-- AlterTable
ALTER TABLE "Session" ADD COLUMN IF NOT EXISTS "familyMemberId" TEXT;

-- CreateIndex
CREATE UNIQUE INDEX IF NOT EXISTS "Session_therapistId_date_time_key" ON "Session"("therapistId", "date", "time");

-- AddForeignKey
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'Session_familyMemberId_fkey'
    ) THEN
        ALTER TABLE "Session" ADD CONSTRAINT "Session_familyMemberId_fkey"
            FOREIGN KEY ("familyMemberId") REFERENCES "FamilyMember"("id")
            ON DELETE SET NULL ON UPDATE CASCADE;
    END IF;
END$$;
