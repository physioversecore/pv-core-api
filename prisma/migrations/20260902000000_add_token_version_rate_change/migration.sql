-- AlterTable
ALTER TABLE "User" ADD COLUMN IF NOT EXISTS "tokenVersion" INTEGER NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE "RateChangeRequest" (
    "id" TEXT NOT NULL,
    "therapistId" TEXT NOT NULL,
    "rateFrom" DOUBLE PRECISION NOT NULL,
    "rateTo" DOUBLE PRECISION NOT NULL,
    "reason" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "adminNotes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "RateChangeRequest_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "RateChangeRequest_therapistId_idx" ON "RateChangeRequest"("therapistId");

-- CreateIndex
CREATE INDEX "RateChangeRequest_status_idx" ON "RateChangeRequest"("status");

-- AddForeignKey
ALTER TABLE "RateChangeRequest" ADD CONSTRAINT "RateChangeRequest_therapistId_fkey" FOREIGN KEY ("therapistId") REFERENCES "Therapist"("id") ON DELETE CASCADE ON UPDATE CASCADE;