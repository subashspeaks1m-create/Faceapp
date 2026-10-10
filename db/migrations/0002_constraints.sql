-- Raw constraints Prisma cannot express (source: docs/migration_constraints.sql).
ALTER TABLE "ImageJob" ADD CONSTRAINT job_intensity CHECK ("intensity" >= 0 AND "intensity" <= 1 AND "intensity" <> 'NaN'::float8);
ALTER TABLE "ImageJob" ADD CONSTRAINT job_revision CHECK ("sourceRevision" >= 0 AND "candidateRevision" >= 0 AND "eventRevision" >= 0 AND "fence" >= 0);
ALTER TABLE "ImageJob" ADD CONSTRAINT job_units CHECK ("reservedUnits" >= 0);
ALTER TABLE "CreditWallet" ADD CONSTRAINT wallet_nonnegative CHECK ("balance" >= 0 AND "reserved" >= 0 AND "reserved" <= "balance");
ALTER TABLE "CreditTransaction" ADD CONSTRAINT credit_units CHECK ("units" >= 0);
ALTER TABLE "CreditTransaction" ADD CONSTRAINT credit_sign CHECK (
  ("kind" IN ('GRANT','REFUND') AND "amount" = "units") OR
  ("kind" = 'SETTLE' AND "amount" = -"units") OR
  ("kind" IN ('RESERVE','RELEASE') AND "amount" = 0)
);
ALTER TABLE "UploadAsset" ADD CONSTRAINT upload_size CHECK ("byteLength" > 0 AND "byteLength" <= 10485760);
ALTER TABLE "ImageJob" ADD CONSTRAINT owned_source FOREIGN KEY ("assetId","userId") REFERENCES "UploadAsset"("id","userId");
ALTER TABLE "UploadAsset" ADD CONSTRAINT owned_consent FOREIGN KEY ("consentReceiptId","userId") REFERENCES "ConsentReceipt"("id","userId");
ALTER TABLE "CreditTransaction" ADD CONSTRAINT owned_credit_job FOREIGN KEY ("jobId","userId") REFERENCES "ImageJob"("id","userId");
ALTER TABLE "AuditLog" ADD CONSTRAINT owned_audit_job FOREIGN KEY ("jobId","userId") REFERENCES "ImageJob"("id","userId");
ALTER TABLE "ImageJob" ADD CONSTRAINT retry_counts CHECK ("attemptCount" >= 0 AND "purgeAttemptCount" >= 0);
ALTER TABLE "ImageJob" ADD CONSTRAINT known_filter CHECK ("filterType" IN ('age_young','age_teen','age_50s','age_70s','smile_subtle','smile_tooth','laugh','gender_feminine','gender_masculine','hair_color','beard_density','beauty_retouch'));
CREATE INDEX job_active_queue ON "ImageJob"("createdAt") WHERE "status" = 'QUEUED' AND "tombstonedAt" IS NULL;
CREATE INDEX outbox_undispatched ON "OutboxEvent"("createdAt") WHERE "dispatchedAt" IS NULL;
-- RLS policies or strict service-layer ownership remain required for every read.
-- AuditLog with userId=NULL is service audit, never a privileged photo data grant.
