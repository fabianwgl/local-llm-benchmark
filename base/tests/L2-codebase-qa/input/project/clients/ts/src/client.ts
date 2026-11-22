import { HttpTransport, type TransportOptions } from "./http";
import { paths } from "./paths";

export { HttpError } from "./http";
export { HEADERS, IDEMPOTENCY_HEADER } from "./constants";

export type JobState = "queued" | "scheduled" | "running" | "paused" | "succeeded" | "dead" | "cancelled";

export interface JobSpec {
  type: string;
  payload: unknown;
  queue?: string;
  priority?: number;
  run_at?: string;
}

export interface Job {
  id: string;
  type: string;
  queue: string;
  state: JobState;
  priority: number;
  run_at: string | null;
  attempts: number;
  payload_size: number;
  created_at: string;
  updated_at: string;
}

export interface Run {
  id: string;
  job_id: string;
  attempt: number;
  owner: string;
  state: "running" | "succeeded" | "failed" | "lost";
  started_at: string;
  finished_at: string | null;
  error: string | null;
}

export interface Page<T> {
  items: T[];
  next: string | null;
}

export interface ListJobsFilter {
  state?: JobState;
  queue?: string;
  limit?: number;
  after?: string;
}

const FINAL: ReadonlySet<JobState> = new Set<JobState>(["succeeded", "dead", "cancelled"]);

export class TesseraClient {
  private readonly http: HttpTransport;

  constructor(baseUrl: string, options: TransportOptions = {}) {
    this.http = new HttpTransport(baseUrl, options);
  }

  createJob(spec: JobSpec, opts: { idempotencyKey?: string } = {}): Promise<Job> {
    return this.http.request("POST", paths.jobs(), { body: spec, idempotent: true, ...opts });
  }

  getJob(id: string): Promise<Job> {
    return this.http.request("GET", paths.job(id));
  }

  listJobs(filter: ListJobsFilter = {}): Promise<Page<Job>> {
    return this.http.request("GET", paths.jobs(), { query: { ...filter } });
  }

  cancelJob(id: string): Promise<Job> {
    return this.http.request("POST", paths.jobAction(id, "cancel"));
  }

  pauseJob(id: string): Promise<Job> {
    return this.http.request("POST", paths.jobAction(id, "pause"));
  }

  resumeJob(id: string): Promise<Job> {
    return this.http.request("POST", paths.jobAction(id, "resume"));
  }

  listRuns(jobId: string): Promise<Page<Run>> {
    return this.http.request("GET", paths.jobRuns(jobId));
  }

  runNow(jobId: string, opts: { idempotencyKey?: string } = {}): Promise<Job> {
    return this.http.request("POST", paths.jobRuns(jobId), { idempotent: true, ...opts });
  }

  triggerJob(jobId: string): Promise<Job> {
    return this.http.request("POST", `${paths.job(jobId)}/trigger`);
  }

  getRun(runId: string): Promise<Run> {
    return this.http.request("GET", paths.run(runId));
  }

  getRunOutput<T = unknown>(runId: string): Promise<T | undefined> {
    return this.http.request("GET", paths.runOutput(runId));
  }

  requeueDeadJob(jobId: string): Promise<Job> {
    return this.http.request("POST", paths.admin.requeue(jobId), { idempotent: true });
  }

  async waitForJob(id: string, { intervalMs = 1000, timeoutMs = 300_000 } = {}): Promise<Job> {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const job = await this.getJob(id);
      if (FINAL.has(job.state)) return job;
      if (Date.now() + intervalMs > deadline) throw new Error(`job ${id} still ${job.state} after ${timeoutMs}ms`);
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
}
