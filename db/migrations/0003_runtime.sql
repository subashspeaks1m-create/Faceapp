-- Runtime constraints and long-poll notification for the Phase 1 backend.
ALTER TABLE "AssetFace" ADD CONSTRAINT owned_face_asset FOREIGN KEY ("assetId","userId") REFERENCES "UploadAsset"("id","userId");
ALTER TABLE "AssetFace" ADD CONSTRAINT face_ordinal CHECK ("ordinal" >= 0 AND "ordinal" < 8);
ALTER TABLE "UploadAsset" ADD CONSTRAINT upload_dimensions CHECK (
  ("normalizedWidth" IS NULL AND "normalizedHeight" IS NULL) OR
  ("normalizedWidth" BETWEEN 1 AND 24000 AND "normalizedHeight" BETWEEN 1 AND 24000)
);
ALTER TABLE "UploadAsset" ADD CONSTRAINT upload_purge_attempts CHECK ("purgeAttemptCount" >= 0);
ALTER TABLE "ImageJob" ADD CONSTRAINT job_stage CHECK ("stage" IN (
  'queued','decode','detect','align','parse','transform','restore','blend','encode','deliver','done'
));
-- A purged job never carries an object pointer, and a result only exists on success.
ALTER TABLE "ImageJob" ADD CONSTRAINT job_result_state CHECK (
  "resultObjectKey" IS NULL OR "status" IN ('SUCCEEDED','EXPIRED','CANCELED')
);
CREATE INDEX job_running_lease ON "ImageJob"("leaseExpiresAt") WHERE "status" IN ('RUNNING','CANCEL_REQUESTED');
CREATE INDEX upload_unpurged ON "UploadAsset"("createdAt") WHERE "purgedAt" IS NULL;

-- Long polling waits on this channel instead of holding a database connection per request.
-- Payload is the opaque job id only.
CREATE FUNCTION portraitlab_notify_job_event() RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify('job_events', NEW."id"::text);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER image_job_event_revision
AFTER UPDATE OF "eventRevision" ON "ImageJob"
FOR EACH ROW WHEN (NEW."eventRevision" IS DISTINCT FROM OLD."eventRevision")
EXECUTE FUNCTION portraitlab_notify_job_event();
