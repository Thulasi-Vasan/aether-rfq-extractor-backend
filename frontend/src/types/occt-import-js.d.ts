declare module "occt-import-js" {
  export interface OcctMesh {
    name?: string;
    color?: [number, number, number];
    attributes: {
      position: { array: number[] };
      normal?: { array: number[] };
    };
    index: { array: number[] };
  }

  export interface OcctResult {
    success: boolean;
    error?: string;
    meshes?: OcctMesh[];
  }

  export interface OcctInstance {
    ReadStepFile(data: Uint8Array, params?: Record<string, unknown>): OcctResult;
  }

  export default function occtImportJs(options?: {
    locateFile?: (path: string) => string;
  }): Promise<OcctInstance>;
}
