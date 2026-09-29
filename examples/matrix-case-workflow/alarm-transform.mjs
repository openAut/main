import { alarmSession } from './workflow.mjs';

// The host supplies the SAME Store instance as registerWorkflow, and an already-approved
// base transform that validates equipment scope, metric types, event identity and timestamps.
export function createCaseTransform(baseTransform, store, { syntheticOnly = true } = {}) {
  return async ctx => {
    const result = await baseTransform(ctx); // Authorize and validate BEFORE creating a case.
    if (!result) return result;
    const event = JSON.parse(ctx.payload.event_json);
    if (syntheticOnly && event.synthetic !== true) return result;
    const row = store.openAlarm(event);
    return { ...result, sessionKey: alarmSession(row), sessionKeySource: 'static', deliver: false,
      message: result.message + '\nÄrende ' + row.id + '. Skriv en kort gruppanalys, högst 1500 tecken. ' +
        'Skilj syntetisk händelse från faktisk process och ge en nästa kontrollfråga.' };
  };
}
