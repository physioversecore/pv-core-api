-- AlterTable
ALTER TABLE "Report" ADD COLUMN     "therapistId" TEXT;

-- AddForeignKey
ALTER TABLE "Report" ADD CONSTRAINT "Report_therapistId_fkey" FOREIGN KEY ("therapistId") REFERENCES "Therapist"("id") ON DELETE SET NULL ON UPDATE CASCADE;
