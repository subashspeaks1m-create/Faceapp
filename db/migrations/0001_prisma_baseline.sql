-- Generated: prisma@6.19.3 migrate diff --from-empty --to-schema-datamodel docs/schema.prisma --script
-- Regenerate after editing docs/schema.prisma; do not hand-edit.
-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateEnum
CREATE TYPE "JobStatus" AS ENUM ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCEL_REQUESTED', 'CANCELED', 'EXPIRED', 'PURGED');

-- CreateEnum
CREATE TYPE "CreditKind" AS ENUM ('GRANT', 'RESERVE', 'SETTLE', 'RELEASE', 'REFUND');

-- CreateTable
CREATE TABLE "User" (
    "id" UUID NOT NULL,
    "externalSubject" VARCHAR(255) NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "deletedAt" TIMESTAMPTZ(6),

    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ConsentReceipt" (
    "id" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "policyVersion" VARCHAR(64) NOT NULL,
    "processorRegion" VARCHAR(64) NOT NULL,
    "purpose" VARCHAR(64) NOT NULL,
    "acceptedAt" TIMESTAMPTZ(6) NOT NULL,
    "withdrawnAt" TIMESTAMPTZ(6),

    CONSTRAINT "ConsentReceipt_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "UploadAsset" (
    "id" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "consentReceiptId" UUID NOT NULL,
    "objectPrefix" TEXT,
    "mimeType" VARCHAR(32) NOT NULL,
    "byteLength" BIGINT NOT NULL,
    "checksumSha256" CHAR(64),
    "normalizedWidth" INTEGER,
    "normalizedHeight" INTEGER,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finalizedAt" TIMESTAMPTZ(6),
    "expiresAt" TIMESTAMPTZ(6) NOT NULL,
    "purgeAttemptCount" INTEGER NOT NULL DEFAULT 0,
    "nextPurgeAt" TIMESTAMPTZ(6),
    "purgedAt" TIMESTAMPTZ(6),

    CONSTRAINT "UploadAsset_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AssetFace" (
    "id" UUID NOT NULL,
    "assetId" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "ordinal" INTEGER NOT NULL,
    "bbox" JSONB NOT NULL,
    "landmarks5" JSONB NOT NULL,
    "score" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AssetFace_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ImageJob" (
    "id" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "assetId" UUID NOT NULL,
    "faceId" UUID NOT NULL,
    "filterType" VARCHAR(48) NOT NULL,
    "intensity" DOUBLE PRECISION NOT NULL,
    "preserveBackground" BOOLEAN NOT NULL DEFAULT true,
    "parameters" JSONB NOT NULL,
    "sourceRevision" INTEGER NOT NULL,
    "candidateRevision" INTEGER NOT NULL,
    "eventRevision" INTEGER NOT NULL DEFAULT 0,
    "status" "JobStatus" NOT NULL DEFAULT 'QUEUED',
    "stage" VARCHAR(16) NOT NULL DEFAULT 'queued',
    "idempotencyKey" VARCHAR(128) NOT NULL,
    "requestHash" CHAR(64) NOT NULL,
    "modelVersion" VARCHAR(128),
    "reservedUnits" INTEGER NOT NULL,
    "fence" INTEGER NOT NULL DEFAULT 0,
    "attemptCount" INTEGER NOT NULL DEFAULT 0,
    "leaseExpiresAt" TIMESTAMPTZ(6),
    "resultObjectKey" TEXT,
    "resultExpiresAt" TIMESTAMPTZ(6),
    "safeErrorCode" VARCHAR(64),
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "startedAt" TIMESTAMPTZ(6),
    "completedAt" TIMESTAMPTZ(6),
    "expiresAt" TIMESTAMPTZ(6) NOT NULL,
    "tombstonedAt" TIMESTAMPTZ(6),
    "deleteRequestedAt" TIMESTAMPTZ(6),
    "purgeAttemptCount" INTEGER NOT NULL DEFAULT 0,
    "nextPurgeAt" TIMESTAMPTZ(6),
    "purgedAt" TIMESTAMPTZ(6),

    CONSTRAINT "ImageJob_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "FilterPreset" (
    "id" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "name" VARCHAR(80) NOT NULL,
    "manifestVersion" VARCHAR(32) NOT NULL,
    "parameters" JSONB NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "FilterPreset_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CreditWallet" (
    "userId" UUID NOT NULL,
    "balance" INTEGER NOT NULL DEFAULT 0,
    "reserved" INTEGER NOT NULL DEFAULT 0,
    "version" INTEGER NOT NULL DEFAULT 0,

    CONSTRAINT "CreditWallet_pkey" PRIMARY KEY ("userId")
);

-- CreateTable
CREATE TABLE "CreditTransaction" (
    "id" UUID NOT NULL,
    "userId" UUID NOT NULL,
    "jobId" UUID,
    "kind" "CreditKind" NOT NULL,
    "amount" INTEGER NOT NULL,
    "units" INTEGER NOT NULL,
    "deduplicationKey" VARCHAR(160) NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "CreditTransaction_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "AuditLog" (
    "id" UUID NOT NULL,
    "userId" UUID,
    "jobId" UUID,
    "action" VARCHAR(64) NOT NULL,
    "requestId" UUID NOT NULL,
    "safeMetadata" JSONB NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "AuditLog_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "OutboxEvent" (
    "id" UUID NOT NULL,
    "aggregateId" UUID NOT NULL,
    "eventType" VARCHAR(64) NOT NULL,
    "payload" JSONB NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "dispatchedAt" TIMESTAMPTZ(6),

    CONSTRAINT "OutboxEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "User_externalSubject_key" ON "User"("externalSubject");

-- CreateIndex
CREATE INDEX "ConsentReceipt_userId_acceptedAt_idx" ON "ConsentReceipt"("userId", "acceptedAt");

-- CreateIndex
CREATE UNIQUE INDEX "ConsentReceipt_id_userId_key" ON "ConsentReceipt"("id", "userId");

-- CreateIndex
CREATE UNIQUE INDEX "UploadAsset_objectPrefix_key" ON "UploadAsset"("objectPrefix");

-- CreateIndex
CREATE INDEX "UploadAsset_expiresAt_purgedAt_idx" ON "UploadAsset"("expiresAt", "purgedAt");

-- CreateIndex
CREATE INDEX "UploadAsset_userId_createdAt_idx" ON "UploadAsset"("userId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "UploadAsset_id_userId_key" ON "UploadAsset"("id", "userId");

-- CreateIndex
CREATE UNIQUE INDEX "AssetFace_id_userId_key" ON "AssetFace"("id", "userId");

-- CreateIndex
CREATE UNIQUE INDEX "AssetFace_assetId_ordinal_key" ON "AssetFace"("assetId", "ordinal");

-- CreateIndex
CREATE INDEX "ImageJob_userId_createdAt_idx" ON "ImageJob"("userId", "createdAt");

-- CreateIndex
CREATE INDEX "ImageJob_status_expiresAt_idx" ON "ImageJob"("status", "expiresAt");

-- CreateIndex
CREATE INDEX "ImageJob_tombstonedAt_purgedAt_idx" ON "ImageJob"("tombstonedAt", "purgedAt");

-- CreateIndex
CREATE INDEX "ImageJob_leaseExpiresAt_status_idx" ON "ImageJob"("leaseExpiresAt", "status");

-- CreateIndex
CREATE INDEX "ImageJob_nextPurgeAt_purgedAt_idx" ON "ImageJob"("nextPurgeAt", "purgedAt");

-- CreateIndex
CREATE UNIQUE INDEX "ImageJob_id_userId_key" ON "ImageJob"("id", "userId");

-- CreateIndex
CREATE UNIQUE INDEX "ImageJob_userId_idempotencyKey_key" ON "ImageJob"("userId", "idempotencyKey");

-- CreateIndex
CREATE UNIQUE INDEX "FilterPreset_userId_name_key" ON "FilterPreset"("userId", "name");

-- CreateIndex
CREATE UNIQUE INDEX "CreditTransaction_deduplicationKey_key" ON "CreditTransaction"("deduplicationKey");

-- CreateIndex
CREATE INDEX "CreditTransaction_userId_createdAt_idx" ON "CreditTransaction"("userId", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "CreditTransaction_jobId_kind_key" ON "CreditTransaction"("jobId", "kind");

-- CreateIndex
CREATE INDEX "AuditLog_jobId_createdAt_idx" ON "AuditLog"("jobId", "createdAt");

-- CreateIndex
CREATE INDEX "AuditLog_userId_createdAt_idx" ON "AuditLog"("userId", "createdAt");

-- CreateIndex
CREATE INDEX "OutboxEvent_dispatchedAt_createdAt_idx" ON "OutboxEvent"("dispatchedAt", "createdAt");

-- AddForeignKey
ALTER TABLE "ConsentReceipt" ADD CONSTRAINT "ConsentReceipt_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UploadAsset" ADD CONSTRAINT "UploadAsset_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "UploadAsset" ADD CONSTRAINT "UploadAsset_consentReceiptId_fkey" FOREIGN KEY ("consentReceiptId") REFERENCES "ConsentReceipt"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AssetFace" ADD CONSTRAINT "AssetFace_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadAsset"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ImageJob" ADD CONSTRAINT "ImageJob_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ImageJob" ADD CONSTRAINT "ImageJob_assetId_fkey" FOREIGN KEY ("assetId") REFERENCES "UploadAsset"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "FilterPreset" ADD CONSTRAINT "FilterPreset_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CreditWallet" ADD CONSTRAINT "CreditWallet_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CreditTransaction" ADD CONSTRAINT "CreditTransaction_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "CreditTransaction" ADD CONSTRAINT "CreditTransaction_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "ImageJob"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "AuditLog" ADD CONSTRAINT "AuditLog_jobId_fkey" FOREIGN KEY ("jobId") REFERENCES "ImageJob"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

