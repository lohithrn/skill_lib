#!/usr/bin/env bash
#
# project_constants.sh — IDENTITY ONLY.
#
# Sourced by every script in the repo. The one place a name is written by hand, and the only
# thing in this file is identity: what this library is called and where its things are named.
#
# Deployment decisions do NOT belong here. ARTIFACT_BUCKET_REGION, ARTIFACT_ACCESS_REGIONS and
# MOUNT_PROPERTIES_FILE are set per stage in z_build_and_publish_<stage>.sh, because a value that
# lives in this file reads as identity and nobody thinks to vary it by stage.

# The only hand-written value. Lower case: it becomes part of an S3 bucket name.
export TENANT_NAME="<tenant>"

# Derived, never retyped. PACKAGE_NAME is the src/ directory, so a rename on disk cannot drift
# from the constant. PROJECT_NAME is the repo directory, lower-cased because S3 rejects uppercase
# in a bucket name and rejects it only at the end of a build.
export PACKAGE_NAME="$(ls src/ 2>/dev/null | head -1)"
export PROJECT_NAME="$(basename "$PWD" | tr '[:upper:]' '[:lower:]')"

# Overridable defaults.
export AWS_PROFILE="${AWS_PROFILE:-${TENANT_NAME}}"
export AWS_REGION="${AWS_REGION:-us-west-2}"          # SDK default only; NOT for bucket creation
export ARTIFACT_CACHE_PREFIX="${ARTIFACT_CACHE_PREFIX:-artifacts}"
export MOUNT_STRATEGY="${MOUNT_STRATEGY:-s3-mountpoint}"   # or efs-native

# ---------------------------------------------------------------------------------------------
# Name builders. Two buckets per stage, and the stage is a required argument in both: a default
# stage is one typo away from publishing beta over prod.
# ---------------------------------------------------------------------------------------------

# Wheel/package bucket: {tenant}-{project}-{stage}
s3_upload_bucket_name() {
    local stage_lower="${1:?stage required}"
    printf "%s-%s-%s" "$TENANT_NAME" "$PROJECT_NAME" "$stage_lower"
}

# Artifact cache bucket: {tenant}-{project}-artifacts-{stage}
artifact_cache_bucket_name() {
    local stage_lower="${1:?stage required}"
    printf "%s-%s-artifacts-%s" "$TENANT_NAME" "$PROJECT_NAME" "$stage_lower"
}

# Mount root: the stage is already in the bucket name, so it is not repeated in the path.
mount_root_path() {
    printf "/mnt/efs/%s-%s/%s" "$TENANT_NAME" "$PROJECT_NAME" "$ARTIFACT_CACHE_PREFIX"
}
