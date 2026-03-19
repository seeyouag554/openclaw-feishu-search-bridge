export default function (api) {
  api.registerTool(
    {
      name: "search_bridge_search",
      description: "通过本地 Search Bridge 执行联网搜索。",
      parameters: {
        type: "object",
        additionalProperties: false,
        properties: {
          query: { type: "string", description: "要搜索的查询词" },
          count: {
            type: "integer",
            description: "返回结果条数，建议 1-10",
            minimum: 1,
            maximum: 10,
            default: 5
          }
        },
        required: ["query"]
      },
      async execute(_id, params) {
        const bridgeBase = process.env.SEARCH_BRIDGE_BASE_URL || "http://127.0.0.1:8787";
        const res = await fetch(`${bridgeBase}/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: params.query, count: params.count ?? 5 })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          return { content: [{ type: "text", text: `search_bridge_search 调用失败: ${JSON.stringify(data)}` }] };
        }
        return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
      }
    },
    { optional: true }
  );

  api.registerTool(
    {
      name: "search_bridge_fetch",
      description: "通过本地 Search Bridge 抓取网页正文。",
      parameters: {
        type: "object",
        additionalProperties: false,
        properties: {
          url: { type: "string", description: "要抓取的网页 URL" }
        },
        required: ["url"]
      },
      async execute(_id, params) {
        const bridgeBase = process.env.SEARCH_BRIDGE_BASE_URL || "http://127.0.0.1:8787";
        const res = await fetch(`${bridgeBase}/fetch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: params.url })
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          return { content: [{ type: "text", text: `search_bridge_fetch 调用失败: ${JSON.stringify(data)}` }] };
        }
        return { content: [{ type: "text", text: JSON.stringify(data, null, 2) }] };
      }
    },
    { optional: true }
  );
}
