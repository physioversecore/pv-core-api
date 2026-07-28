-- CreateTable
CREATE TABLE "EmailVerification" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "code" TEXT NOT NULL,
    "purpose" TEXT NOT NULL DEFAULT 'signup',
    "expiresAt" TIMESTAMP(3) NOT NULL,
    "used" BOOLEAN NOT NULL DEFAULT false,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EmailVerification_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "EmailVerification_email_purpose_idx" ON "EmailVerification"("email", "purpose");

-- CreateIndex
CREATE INDEX "EmailVerification_expiresAt_idx" ON "EmailVerification"("expiresAt");
