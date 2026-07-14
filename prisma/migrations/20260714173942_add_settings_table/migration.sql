-- CreateTable
CREATE TABLE "Setting" (
    "key" TEXT NOT NULL,
    "jsonValue" TEXT NOT NULL,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Setting_pkey" PRIMARY KEY ("key")
);
