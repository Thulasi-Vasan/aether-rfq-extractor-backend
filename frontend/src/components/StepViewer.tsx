import { Box, Camera, Crosshair, RotateCcw, Ruler, Square } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import occtImportJs from "occt-import-js";
import occtWasmUrl from "occt-import-js/dist/occt-import-js.wasm?url";
import { formatNumber } from "../lib/format";

type ViewPreset = "iso" | "front" | "back" | "top" | "bottom" | "left" | "right";

interface StepViewerProps {
  stepUrl: string;
}

export function StepViewer({ stepUrl }: StepViewerProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const modelRef = useRef<THREE.Group | null>(null);
  const gridRef = useRef<THREE.GridHelper | null>(null);
  const measurementRef = useRef<THREE.Group | null>(null);
  const raycasterRef = useRef(new THREE.Raycaster());
  const pointerRef = useRef(new THREE.Vector2());
  const measurePointsRef = useRef<THREE.Vector3[]>([]);
  const [wireframe, setWireframe] = useState(false);
  const [measureMode, setMeasureMode] = useState(false);
  const [distance, setDistance] = useState<number | null>(null);
  const [status, setStatus] = useState("Loading STEP model...");
  const [error, setError] = useState<string | null>(null);

  const viewPresets = useMemo(
    () => [
      ["iso", "Iso"],
      ["front", "Front"],
      ["top", "Top"],
      ["right", "Right"],
    ] as Array<[ViewPreset, string]>,
    [],
  );

  const fitCameraToObject = useCallback((preset: ViewPreset = "iso") => {
    const camera = cameraRef.current;
    const controls = controlsRef.current;
    const model = modelRef.current;
    if (!camera || !controls || !model) {
      return;
    }

    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const radius = Math.max(size.x, size.y, size.z, 1);
    const distanceFromCenter = radius * 2.15;

    const directions: Record<ViewPreset, THREE.Vector3> = {
      iso: new THREE.Vector3(1.15, -1.35, 0.9),
      front: new THREE.Vector3(0, -1, 0),
      back: new THREE.Vector3(0, 1, 0),
      top: new THREE.Vector3(0, 0, 1),
      bottom: new THREE.Vector3(0, 0, -1),
      left: new THREE.Vector3(-1, 0, 0),
      right: new THREE.Vector3(1, 0, 0),
    };

    const direction = directions[preset].normalize();
    camera.position.copy(center).add(direction.multiplyScalar(distanceFromCenter));
    camera.near = Math.max(distanceFromCenter / 100, 0.1);
    camera.far = distanceFromCenter * 100;
    camera.up.set(0, 0, 1);
    camera.lookAt(center);
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
  }, []);

  const clearMeasurement = useCallback(() => {
    measurePointsRef.current = [];
    setDistance(null);
    measurementRef.current?.clear();
  }, []);

  const resetViewer = useCallback(() => {
    clearMeasurement();
    setMeasureMode(false);
    fitCameraToObject("iso");
  }, [clearMeasurement, fitCameraToObject]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) {
      return;
    }

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf5f7fb);
    sceneRef.current = scene;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    rendererRef.current = renderer;
    mount.appendChild(renderer.domElement);

    const camera = new THREE.PerspectiveCamera(42, mount.clientWidth / mount.clientHeight, 0.1, 100000);
    camera.position.set(300, -420, 260);
    camera.up.set(0, 0, 1);
    cameraRef.current = camera;

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controlsRef.current = controls;

    scene.add(new THREE.HemisphereLight(0xffffff, 0xd7dce5, 2.2));
    const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
    keyLight.position.set(250, -300, 500);
    scene.add(keyLight);
    const fillLight = new THREE.DirectionalLight(0xcbd8ff, 1.1);
    fillLight.position.set(-350, 260, 280);
    scene.add(fillLight);

    const grid = new THREE.GridHelper(500, 20, 0xd4dae4, 0xe8ecf3);
    grid.rotateX(Math.PI / 2);
    gridRef.current = grid;
    scene.add(grid);

    const measurementGroup = new THREE.Group();
    measurementRef.current = measurementGroup;
    scene.add(measurementGroup);

    let disposed = false;

    async function loadStep() {
      setStatus("Loading STEP model...");
      setError(null);
      clearMeasurement();
      try {
        const [occt, response] = await Promise.all([
          occtImportJs({ locateFile: () => occtWasmUrl }),
          fetch(stepUrl),
        ]);
        if (!response.ok) {
          throw new Error(`Could not download STEP file: HTTP ${response.status}`);
        }

        const buffer = await response.arrayBuffer();
        const result = occt.ReadStepFile(new Uint8Array(buffer), {
          linearUnit: "millimeter",
          linearDeflectionType: "bounding_box_ratio",
          linearDeflection: 0.001,
          angularDeflection: 0.5,
        });

        if (!result.success || !result.meshes?.length) {
          throw new Error(result.error ?? "STEP parser returned no meshes.");
        }

        const group = new THREE.Group();
        for (const resultMesh of result.meshes) {
          const geometry = new THREE.BufferGeometry();
          geometry.setAttribute(
            "position",
            new THREE.Float32BufferAttribute(resultMesh.attributes.position.array, 3),
          );
          if (resultMesh.attributes.normal) {
            geometry.setAttribute(
              "normal",
              new THREE.Float32BufferAttribute(resultMesh.attributes.normal.array, 3),
            );
          } else {
            geometry.computeVertexNormals();
          }
          if (resultMesh.index?.array) {
            geometry.setIndex(new THREE.BufferAttribute(Uint32Array.from(resultMesh.index.array), 1));
          }
          geometry.computeBoundingBox();

          const color = resultMesh.color
            ? new THREE.Color(resultMesh.color[0], resultMesh.color[1], resultMesh.color[2])
            : new THREE.Color(0x9aa7b8);
          const material = new THREE.MeshStandardMaterial({
            color,
            metalness: 0.02,
            roughness: 0.38,
            side: THREE.DoubleSide,
            transparent: true,
          });
          const mesh = new THREE.Mesh(geometry, material);
          mesh.name = resultMesh.name ?? "STEP mesh";
          group.add(mesh);

          const edgeGeometry = new THREE.EdgesGeometry(geometry, 35);
          const edges = new THREE.LineSegments(
            edgeGeometry,
            new THREE.LineBasicMaterial({ color: 0x334155, transparent: true, opacity: 0.16 }),
          );
          edges.name = "model-edges";
          group.add(edges);
        }

        if (disposed) {
          return;
        }

        modelRef.current?.removeFromParent();
        modelRef.current = group;
        scene.add(group);
        positionGridUnderModel(group);
        setStatus(`${result.meshes.length} mesh${result.meshes.length === 1 ? "" : "es"} loaded`);
        fitCameraToObject("iso");
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Unable to render STEP file.");
        setStatus("STEP viewer failed");
      }
    }

    loadStep();

    const resizeObserver = new ResizeObserver(() => {
      const width = mount.clientWidth;
      const height = mount.clientHeight;
      renderer.setSize(width, height);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    });
    resizeObserver.observe(mount);

    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
    };
    renderer.setAnimationLoop(animate);

    return () => {
      disposed = true;
      resizeObserver.disconnect();
      renderer.setAnimationLoop(null);
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      scene.traverse((object) => {
        if (object instanceof THREE.Mesh || object instanceof THREE.LineSegments) {
          object.geometry.dispose();
          const materials = Array.isArray(object.material) ? object.material : [object.material];
          materials.forEach((material) => material.dispose());
        }
      });
    };
  }, [clearMeasurement, fitCameraToObject, stepUrl]);

  const positionGridUnderModel = (model: THREE.Object3D) => {
    const grid = gridRef.current;
    if (!grid) {
      return;
    }
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const maxSize = Math.max(size.x, size.y, size.z, 1);
    const gridSize = Math.ceil((maxSize * 2.4) / 50) * 50;
    const divisions = Math.max(10, Math.min(40, Math.round(gridSize / 25)));
    const newGrid = new THREE.GridHelper(gridSize, divisions, 0xd4dae4, 0xe8ecf3);
    newGrid.rotateX(Math.PI / 2);
    newGrid.position.z = box.min.z - maxSize * 0.08;
    newGrid.position.x = box.getCenter(new THREE.Vector3()).x;
    newGrid.position.y = box.getCenter(new THREE.Vector3()).y;
    grid.parent?.add(newGrid);
    grid.parent?.remove(grid);
    grid.geometry.dispose();
    if (Array.isArray(grid.material)) {
      grid.material.forEach((material) => material.dispose());
    } else {
      grid.material.dispose();
    }
    gridRef.current = newGrid;
  };

  useEffect(() => {
    modelRef.current?.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        const materials = Array.isArray(object.material) ? object.material : [object.material];
        materials.forEach((material) => {
          if (material instanceof THREE.MeshStandardMaterial) {
            material.wireframe = false;
            material.opacity = wireframe ? (measureMode ? 0.1 : 0.18) : measureMode ? 0.72 : 1;
            material.depthWrite = !(wireframe || measureMode);
          }
        });
      }
      if (object.name === "model-edges") {
        object.visible = true;
        const line = object as THREE.LineSegments;
        if (line.material instanceof THREE.LineBasicMaterial) {
          line.material.opacity = wireframe ? (measureMode ? 0.34 : 0.58) : measureMode ? 0.08 : 0.16;
          line.material.color.set(wireframe ? 0x475569 : 0x334155);
        }
      }
    });
  }, [measureMode, wireframe]);

  const handlePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!measureMode || !modelRef.current || !cameraRef.current || !mountRef.current) {
      return;
    }

    const bounds = mountRef.current.getBoundingClientRect();
    pointerRef.current.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1;
    pointerRef.current.y = -(((event.clientY - bounds.top) / bounds.height) * 2 - 1);
    raycasterRef.current.setFromCamera(pointerRef.current, cameraRef.current);

    const targets: THREE.Object3D[] = [];
    modelRef.current.traverse((object) => {
      if (object instanceof THREE.Mesh) {
        targets.push(object);
      }
    });
    const hit = raycasterRef.current.intersectObjects(targets, false)[0];
    if (!hit) {
      return;
    }

    const nextPoints = [...measurePointsRef.current, hit.point.clone()].slice(-2);
    measurePointsRef.current = nextPoints;
    renderMeasurement(nextPoints);
    if (nextPoints.length === 2) {
      setDistance(nextPoints[0].distanceTo(nextPoints[1]));
    } else {
      setDistance(null);
    }
  };

  const renderMeasurement = (points: THREE.Vector3[]) => {
    const group = measurementRef.current;
    if (!group) {
      return;
    }
    group.clear();
    const markerMaterial = new THREE.MeshBasicMaterial({ color: 0x0f766e, depthTest: false });
    const haloMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0.78,
      depthTest: false,
    });
    points.forEach((point) => {
      const halo = new THREE.Mesh(new THREE.SphereGeometry(5.2, 20, 20), haloMaterial);
      halo.position.copy(point);
      halo.renderOrder = 8;
      group.add(halo);

      const marker = new THREE.Mesh(new THREE.SphereGeometry(3.3, 20, 20), markerMaterial);
      marker.position.copy(point);
      marker.renderOrder = 9;
      group.add(marker);
    });
    if (points.length === 2) {
      const line = buildMeasurementCylinder(points[0], points[1]);
      group.add(line);
      group.add(buildDistanceLabel(points[0], points[1]));
    }
  };

  return (
    <div className="step-viewer">
      <div className="viewer-toolbar">
        <button type="button" onClick={() => setWireframe((value) => !value)} className={wireframe ? "active" : ""}>
          {wireframe ? <Box size={15} /> : <Square size={15} />}
          {wireframe ? "Wireframe" : "Solid"}
        </button>
        <button
          type="button"
          onClick={() => {
            setMeasureMode((value) => !value);
            clearMeasurement();
          }}
          className={measureMode ? "active" : ""}
        >
          <Ruler size={15} />
          Measure
        </button>
        <button type="button" onClick={resetViewer}>
          <RotateCcw size={15} />
          Reset
        </button>
        <div className="view-menu">
          <Camera size={15} />
          {viewPresets.map(([preset, label]) => (
            <button key={preset} type="button" onClick={() => fitCameraToObject(preset)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div
        className={`step-canvas ${measureMode ? "measuring" : ""}`}
        ref={mountRef}
        onPointerDown={handlePointerDown}
      />

      <div className="viewer-status">
        <span>
          <Crosshair size={14} />
          {error ?? status}
        </span>
        <strong>{measureMode ? `Distance: ${formatNumber(distance, 3)} mm` : "Orbit: drag / zoom"}</strong>
      </div>
    </div>
  );
}

function buildMeasurementCylinder(start: THREE.Vector3, end: THREE.Vector3): THREE.Mesh {
  const direction = new THREE.Vector3().subVectors(end, start);
  const length = direction.length();
  const geometry = new THREE.CylinderGeometry(1.15, 1.15, length, 14);
  const material = new THREE.MeshBasicMaterial({
    color: 0x0f766e,
    depthTest: false,
  });
  const cylinder = new THREE.Mesh(geometry, material);
  cylinder.position.copy(start).add(end).multiplyScalar(0.5);
  cylinder.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction.normalize());
  cylinder.renderOrder = 10;
  return cylinder;
}

function buildDistanceLabel(start: THREE.Vector3, end: THREE.Vector3): THREE.Sprite {
  const distance = start.distanceTo(end);
  const text = `${formatNumber(distance, 3)} mm`;
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 80;
  const context = canvas.getContext("2d");
  if (context) {
    context.fillStyle = "rgba(15, 118, 110, 0.94)";
    context.roundRect(8, 12, 240, 48, 10);
    context.fill();
    context.fillStyle = "#ffffff";
    context.font = "700 24px Inter, Arial, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(text, 128, 36);
  }
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthTest: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.position.copy(start).add(end).multiplyScalar(0.5);
  sprite.position.z += 12;
  sprite.scale.set(62, 19, 1);
  sprite.renderOrder = 11;
  return sprite;
}
