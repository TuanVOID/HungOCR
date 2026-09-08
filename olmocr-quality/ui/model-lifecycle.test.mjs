import test from "node:test";
import assert from "node:assert/strict";
import { ModelLifecycle } from "./model-lifecycle.mjs";

function fixture() {
  const data = {
    time: 0,
    busy: false,
    observation: { ready: true, running: false, counter: 0 },
    starts: 0,
    stops: 0,
  };
  const model = new ModelLifecycle({
    now: () => data.time,
    busy: () => data.busy,
    probe: async () => data.observation,
    start: async () => {
      data.starts++;
      data.observation = { ready: true, running: false, counter: 0 };
    },
    stop: async () => {
      data.stops++;
      data.observation = { ready: false };
    },
  });
  return { data, model };
}
test("unloads at five minutes; polling does not extend idle; reloads on demand", async () => {
  const { data, model } = fixture();
  for (data.time = 0; data.time < 300000; data.time += 1000) await model.tick();
  assert.equal(data.stops, 0);
  await model.tick();
  assert.equal(data.stops, 1);
  await Promise.all([model.ensureReady(), model.ensureReady()]);
  assert.equal(data.starts, 1);
  assert.equal(model.state, "ready");
});
test("job lease protects gaps between pages and completion resets timeout", async () => {
  const { data, model } = fixture();
  data.busy = true;
  data.time = 600000;
  await model.tick();
  assert.equal(data.stops, 0);
  data.busy = false;
  model.touch();
  data.time += 299999;
  await model.tick();
  assert.equal(data.stops, 0);
  data.time++;
  await model.tick();
  assert.equal(data.stops, 1);
});
test("direct vLLM requests and changed counters extend idle", async () => {
  const { data, model } = fixture();
  await model.tick();
  data.time = 300000;
  data.observation.running = true;
  await model.tick();
  data.time = 600000;
  data.observation.running = false;
  data.observation.counter++;
  await model.tick();
  assert.equal(data.stops, 0);
  data.time += 300000;
  await model.tick();
  assert.equal(data.stops, 1);
});
test("unknown metrics never trigger shutdown", async () => {
  const { data, model } = fixture();
  data.time = 900000;
  data.observation = null;
  await model.tick();
  assert.equal(data.stops, 0);
});
test("a request arriving during shutdown waits then reloads", async () => {
  const { data, model } = fixture();
  let finishStop;
  model.stop = () =>
    new Promise((resolve) => {
      finishStop = () => {
        data.observation = { ready: false };
        resolve();
      };
    });
  data.time = 300000;
  const stopping = model.tick();
  await new Promise((resolve) => setImmediate(resolve));
  const loading = model.ensureReady();
  finishStop();
  await Promise.all([stopping, loading]);
  assert.equal(data.starts, 1);
  assert.equal(model.state, "ready");
});
test("load failures are retryable", async () => {
  const { data, model } = fixture();
  data.observation = { ready: false };
  const start = model.start;
  model.start = async () => {
    throw new Error("load failure");
  };
  await assert.rejects(model.ensureReady(), /load failure/);
  assert.equal(model.state, "error");
  model.start = start;
  await model.ensureReady();
  assert.equal(model.state, "ready");
});
