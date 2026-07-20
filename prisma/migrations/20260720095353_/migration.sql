-- AlterTable
ALTER TABLE "Payment" ADD COLUMN     "billingCountry" TEXT,
ADD COLUMN     "cardLast4" TEXT,
ADD COLUMN     "currency" TEXT NOT NULL DEFAULT 'NPR',
ADD COLUMN     "paymentType" TEXT,
ADD COLUMN     "platformFee" DOUBLE PRECISION NOT NULL DEFAULT 0,
ADD COLUMN     "transactionRef" TEXT,
ADD COLUMN     "walletMobile" TEXT;
