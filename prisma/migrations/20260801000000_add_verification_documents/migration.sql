-- AlterTable
ALTER TABLE "Therapist" ADD COLUMN     "licenseNumber" TEXT;
-- AlterTable
ALTER TABLE "Verification" ADD COLUMN     "documentUrl" TEXT;
ALTER TABLE "Verification" ADD COLUMN     "fileName" TEXT;
ALTER TABLE "Verification" ADD COLUMN     "fileSize" INTEGER;
