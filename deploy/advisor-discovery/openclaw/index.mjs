import { createReadTool } from './read-tool.mjs';

export default {
  id:'openaut-read',name:'openAut scoped reader',
  description:'Area-scoped metadata, telemetry and verified Forge sources.',
  register(api) { api.registerTool(createReadTool(),{optional:true}); },
};
