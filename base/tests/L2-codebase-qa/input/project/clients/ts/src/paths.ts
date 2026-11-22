import { API_VERSION } from "./constants";

const base = `/${API_VERSION}`;
const enc = encodeURIComponent;

export type JobAction = "cancel" | "pause" | "resume";

export const paths = {
  jobs: () => `${base}/jobs`,
  job: (id: string) => `${base}/jobs/${enc(id)}`,
  jobAction: (id: string, action: JobAction) => `${base}/jobs/${enc(id)}/${action}`,
  jobRuns: (id: string) => `${base}/jobs/${enc(id)}/runs`,
  run: (id: string) => `${base}/runs/${enc(id)}`,
  runOutput: (id: string) => `${base}/runs/${enc(id)}/output`,
  admin: {
    leader: () => `${base}/admin/leader`,
    deadLetters: () => `${base}/admin/dead-letters`,
    requeue: (id: string) => `${base}/admin/jobs/${enc(id)}/requeue`,
    drain: () => `${base}/admin/drain`,
  },
};
