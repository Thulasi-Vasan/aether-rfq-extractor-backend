"""boto3 Bedrock-runtime client factory."""
from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import get_settings


@lru_cache
def get_bedrock_client():
    """Return a cached bedrock-runtime client built from settings.

    Credentials follow the standard AWS chain (env vars, shared config,
    instance role, ...). An optional named profile can be set via AWS_PROFILE.
    """
    settings = get_settings()
    session = boto3.Session(
        profile_name=settings.aws_profile,
        region_name=settings.bedrock_region,
    )
    # Detailed process plans can take well over boto3's default 60s read
    # timeout, so extend it. One retry guards against transient blips.
    config = Config(
        read_timeout=settings.machining_bedrock_read_timeout_s,
        connect_timeout=10,
        retries={"max_attempts": 2, "mode": "standard"},
    )
    return session.client("bedrock-runtime", config=config)
