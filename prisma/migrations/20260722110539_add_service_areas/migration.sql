-- CreateTable
CREATE TABLE "ServiceArea" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "localities" JSONB NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'Active',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "ServiceArea_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "TherapistServiceArea" (
    "id" TEXT NOT NULL,
    "therapistId" TEXT NOT NULL,
    "serviceAreaId" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "TherapistServiceArea_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ServiceArea_name_idx" ON "ServiceArea"("name");

-- CreateIndex
CREATE INDEX "ServiceArea_status_idx" ON "ServiceArea"("status");

-- CreateIndex
CREATE INDEX "TherapistServiceArea_therapistId_idx" ON "TherapistServiceArea"("therapistId");

-- CreateIndex
CREATE INDEX "TherapistServiceArea_serviceAreaId_idx" ON "TherapistServiceArea"("serviceAreaId");

-- CreateIndex
CREATE UNIQUE INDEX "TherapistServiceArea_therapistId_serviceAreaId_key" ON "TherapistServiceArea"("therapistId", "serviceAreaId");

-- AddForeignKey
ALTER TABLE "TherapistServiceArea" ADD CONSTRAINT "TherapistServiceArea_therapistId_fkey" FOREIGN KEY ("therapistId") REFERENCES "Therapist"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "TherapistServiceArea" ADD CONSTRAINT "TherapistServiceArea_serviceAreaId_fkey" FOREIGN KEY ("serviceAreaId") REFERENCES "ServiceArea"("id") ON DELETE CASCADE ON UPDATE CASCADE;
