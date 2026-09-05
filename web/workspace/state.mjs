export function activeScheme(project) {
  return project?.schemes?.length === 1 ? project.schemes[0] : null;
}

export function validCalibration(project) {
  const frame = project?.calibration?.product_frame;
  return Number.isFinite(project?.calibration?.width_mm) && project.calibration.width_mm > 0 &&
    Number.isFinite(frame?.w) && frame.w > 0 && Number.isFinite(frame?.h) && frame.h > 0;
}

export function nextPrimaryAction(project) {
  if (!project) return 'create-task';
  if (!project.inputs?.bag_image) return 'upload-bag';
  if (!project.inputs?.logo_source) return 'upload-logo';
  if (!project.asset?.selected_candidate_ids?.length || !project.inputs?.logo_preview) return 'choose-logo';
  if (!validCalibration(project)) return 'calibrate';
  if (!activeScheme(project)) return 'place-logo';
  return 'export-customer';
}

export function canCustomerExport(project) {
  return nextPrimaryAction(project) === 'export-customer';
}

export function suggestedFilename(project) {
  return `${project?.name || 'LogoMock'}_效果图.png`;
}
