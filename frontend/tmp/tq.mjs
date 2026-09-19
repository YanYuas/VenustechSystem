// src/utils/offlineQueueCore.ts
var sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function createQueueManager(opts) {
  const intervalMs = opts.intervalMs ?? 500;
  const maxRetries = opts.maxRetries ?? 3;
  let flushing = false;
  async function counts() {
    const items = await opts.storage.all();
    return {
      pending: items.length,
      failed: items.filter((i) => i.retries >= maxRetries).length
    };
  }
  async function notify(state) {
    const c = await counts();
    opts.onStateChange?.(state, c);
  }
  return {
    intervalMs,
    maxRetries,
    /** 入队一条写操作 */
    async enqueue(entry) {
      const id = await opts.storage.add({ ...entry, createdAt: Date.now(), retries: 0 });
      await notify("idle");
      return id;
    },
    /** 待同步条数 */
    pending: async () => (await counts()).pending,
    /** 失败条数（达到重试上限） */
    failed: async () => (await counts()).failed,
    /**
     * 按 FIFO 重放队列。
     * - 成功 → 出队
     * - 失败 → retries+1；达到 maxRetries 则保留为失败态并**停止本轮**
     *   （避免后续条目在同一个坏端点上空转）
     */
    async flush() {
      if (flushing) return { sent: 0, failed: 0, stopped: false };
      flushing = true;
      let sent = 0;
      let failed2 = 0;
      let stopped = false;
      try {
        await notify("flushing");
        const items = (await opts.storage.all()).sort(
          (a, b) => a.createdAt - b.createdAt || (a.id ?? 0) - (b.id ?? 0)
        );
        for (let i = 0; i < items.length; i++) {
          const entry = items[i];
          if (entry.id === void 0) continue;
          if (entry.retries >= maxRetries) {
            failed2 += 1;
            continue;
          }
          try {
            await opts.send(entry);
            await opts.storage.remove(entry.id);
            sent += 1;
            await notify("flushing");
            if (i < items.length - 1) await sleep(intervalMs);
          } catch (e) {
            const msg = e instanceof Error ? e.message : String(e);
            entry.retries += 1;
            entry.lastError = msg;
            await opts.storage.update(entry);
            opts.onItemFailed?.(entry, msg);
            if (entry.retries >= maxRetries) {
              failed2 += 1;
              stopped = true;
              break;
            }
          }
        }
        const state = failed2 > 0 ? "failed" : "done";
        await notify(state);
        return { sent, failed: failed2, stopped };
      } finally {
        flushing = false;
      }
    },
    /** 手动「重试全部」：把失败条目的重试计数清零后重放 */
    async retryAll() {
      const items = await opts.storage.all();
      for (const it of items) {
        if (it.retries >= maxRetries) {
          it.retries = 0;
          it.lastError = void 0;
          await opts.storage.update(it);
        }
      }
      return this.flush();
    },
    /** 手动「清空失败」 */
    async clearFailed() {
      const n = await opts.storage.removeFailed(maxRetries);
      await notify("idle");
      return n;
    },
    /** 面板数据 */
    list: async () => (await opts.storage.all()).sort(
      (a, b) => a.createdAt - b.createdAt || (a.id ?? 0) - (b.id ?? 0)
    )
  };
}

// scripts/test-offline-queue.ts
var passed = 0;
var failed = 0;
function check(name, cond, extra = "") {
  if (cond) {
    passed += 1;
    console.log(`  \u2705 ${name}`);
  } else {
    failed += 1;
    console.log(`  \u274C ${name} ${extra}`);
  }
}
function memoryStorage() {
  let seq = 0;
  const rows = [];
  return {
    async add(entry) {
      const id = ++seq;
      rows.push({ ...entry, id });
      return id;
    },
    async all() {
      return rows.map((r) => ({ ...r }));
    },
    async update(entry) {
      const i = rows.findIndex((r) => r.id === entry.id);
      if (i >= 0) rows[i] = { ...entry };
    },
    async remove(id) {
      const i = rows.findIndex((r) => r.id === id);
      if (i >= 0) rows.splice(i, 1);
    },
    async removeFailed(maxRetries) {
      let n = 0;
      for (let i = rows.length - 1; i >= 0; i--) {
        if (rows[i].retries >= maxRetries) {
          rows.splice(i, 1);
          n += 1;
        }
      }
      return n;
    },
    dump: () => rows.map((r) => ({ ...r }))
  };
}
async function main() {
  console.log("\u79BB\u7EBF\u961F\u5217\u6838\u5FC3\u6D4B\u8BD5\uFF08mod-tools F4.3\uFF09");
  {
    const storage = memoryStorage();
    const sent = [];
    const mgr = createQueueManager({
      storage,
      send: async (e) => {
        sent.push(e.path);
        return {};
      },
      intervalMs: 1
    });
    await mgr.enqueue({ path: "/assistant/apply", method: "POST", body: { a: 1 }, label: "AI \u52A9\u7406 \xB7 \u52A0\u5165\u5F85\u529E" });
    const items = await mgr.list();
    const it = items[0];
    check(
      "\u5165\u961F\u6761\u76EE\u542B \u8DEF\u5F84/\u65B9\u6CD5/\u8BF7\u6C42\u4F53/\u65F6\u95F4\u6233/\u91CD\u8BD5\u6B21\u6570",
      items.length === 1 && it.path === "/assistant/apply" && it.method === "POST" && JSON.stringify(it.body) === '{"a":1}' && typeof it.createdAt === "number" && it.retries === 0,
      JSON.stringify(it)
    );
    check("pending \u8BA1\u6570\u6B63\u786E", await mgr.pending() === 1, String(await mgr.pending()));
  }
  {
    const storage = memoryStorage();
    const sent = [];
    const mgr = createQueueManager({
      storage,
      send: async (e) => {
        sent.push(e.path);
        return {};
      },
      intervalMs: 1
    });
    await mgr.enqueue({ path: "/p1", method: "POST", body: {} });
    await new Promise((r) => setTimeout(r, 2));
    await mgr.enqueue({ path: "/p2", method: "PATCH", body: {} });
    await new Promise((r) => setTimeout(r, 2));
    await mgr.enqueue({ path: "/p3", method: "DELETE" });
    const res = await mgr.flush();
    check("FIFO \u987A\u5E8F\u91CD\u653E", sent.join(",") === "/p1,/p2,/p3", sent.join(","));
    check("\u91CD\u653E\u6210\u529F\u5168\u90E8\u51FA\u961F", res.sent === 3 && await mgr.pending() === 0, JSON.stringify(res));
  }
  {
    const storage = memoryStorage();
    let calls = 0;
    const mgr = createQueueManager({
      storage,
      send: async () => {
        calls += 1;
        throw new Error("\u7F51\u7EDC\u9519\u8BEF");
      },
      intervalMs: 1,
      maxRetries: 3
    });
    await mgr.enqueue({ path: "/will-fail", method: "POST", body: {} });
    const first = await mgr.flush();
    check(
      "\u5931\u8D25\u540E\u6761\u76EE\u4FDD\u7559\u4E14\u91CD\u8BD5\u6B21\u6570 +1",
      first.failed === 1 && (await mgr.list())[0].retries === 1,
      JSON.stringify(await mgr.list())
    );
    const second = await mgr.flush();
    check("\u7B2C\u4E8C\u6B21\u91CD\u653E\u5931\u8D25 \u2192 2 \u6B21", second.failed === 1 && (await mgr.list())[0].retries === 2, "");
    const third = await mgr.flush();
    const item = (await mgr.list())[0];
    check(
      "\u8FBE\u5230 3 \u6B21\u4E0A\u9650 \u2192 \u6807\u8BB0\u5931\u8D25\u5E76\u505C\u6B62\u672C\u8F6E",
      third.stopped === true && item.retries === 3 && item.lastError?.includes("\u7F51\u7EDC\u9519\u8BEF"),
      JSON.stringify(item)
    );
    const callsBefore = calls;
    await mgr.flush();
    check("\u5DF2\u8FBE\u4E0A\u9650\u7684\u6761\u76EE\u4E0D\u88AB\u81EA\u52A8\u91CD\u653E", calls === callsBefore, `${calls} vs ${callsBefore}`);
    const retried = await mgr.retryAll();
    check("\u91CD\u8BD5\u5168\u90E8\u4F1A\u518D\u6B21\u5C1D\u8BD5\u5931\u8D25\u6761\u76EE", retried.failed === 1 && calls > callsBefore, "");
    const cleared = await mgr.clearFailed();
    check("\u6E05\u7A7A\u5931\u8D25\u79FB\u9664\u6761\u76EE", cleared === 1 && await mgr.pending() === 0, String(cleared));
  }
  {
    const storage = memoryStorage();
    const mgr = createQueueManager({
      storage,
      send: async (e) => {
        if (e.path === "/bad") throw new Error("500");
        return {};
      },
      intervalMs: 1
    });
    await mgr.enqueue({ path: "/good1", method: "POST", body: {} });
    await mgr.enqueue({ path: "/bad", method: "POST", body: {} });
    await mgr.enqueue({ path: "/good2", method: "POST", body: {} });
    const res = await mgr.flush();
    const left = await mgr.list();
    check(
      "\u90E8\u5206\u6210\u529F\uFF1A2 \u6210\u529F 1 \u4FDD\u7559",
      res.sent === 2 && left.length === 1 && left[0].path === "/bad",
      JSON.stringify({ res, left: left.map((l) => l.path) })
    );
  }
  {
    const storage = memoryStorage();
    const mgr1 = createQueueManager({ storage, send: async () => ({}), intervalMs: 1 });
    await mgr1.enqueue({ path: "/persist-me", method: "POST", body: { x: 1 } });
    const mgr2 = createQueueManager({ storage, send: async () => ({}), intervalMs: 1 });
    const items = await mgr2.list();
    check(
      "\u91CD\u542F\u540E\u961F\u5217\u4ECD\u5728\uFF08\u540C\u4E00\u6301\u4E45\u5B58\u50A8\uFF09",
      items.length === 1 && items[0].path === "/persist-me",
      JSON.stringify(items)
    );
  }
  {
    const storage = memoryStorage();
    const stamps = [];
    const mgr = createQueueManager({
      storage,
      send: async () => {
        stamps.push(Date.now());
        return {};
      },
      intervalMs: 40
    });
    await mgr.enqueue({ path: "/s1", method: "POST", body: {} });
    await mgr.enqueue({ path: "/s2", method: "POST", body: {} });
    await mgr.flush();
    const gap = stamps.length === 2 ? stamps[1] - stamps[0] : -1;
    check("\u91CD\u653E\u6761\u76EE\u4E4B\u95F4\u6709\u95F4\u9694\uFF08\u9ED8\u8BA4 500ms \u53EF\u914D\uFF09", gap >= 35, `gap=${gap}ms`);
  }
  {
    const storage = memoryStorage();
    let concurrent = 0;
    let maxConcurrent = 0;
    const mgr = createQueueManager({
      storage,
      send: async () => {
        concurrent += 1;
        maxConcurrent = Math.max(maxConcurrent, concurrent);
        await new Promise((r) => setTimeout(r, 10));
        concurrent -= 1;
        return {};
      },
      intervalMs: 1
    });
    await mgr.enqueue({ path: "/c1", method: "POST", body: {} });
    await Promise.all([mgr.flush(), mgr.flush()]);
    check("\u5E76\u53D1 flush \u4E0D\u4F1A\u91CD\u590D\u53D1\u9001", maxConcurrent === 1, `maxConcurrent=${maxConcurrent}`);
  }
  console.log(`
\u79BB\u7EBF\u961F\u5217\u6D4B\u8BD5\u7ED3\u679C: ${passed} \u901A\u8FC7, ${failed} \u5931\u8D25`);
  process.exit(failed === 0 ? 0 : 1);
}
void main();
