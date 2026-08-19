// Local forwarding proxy that records BOTH the exact request (headers+body)
// and the RAW (decompressed) upstream response body for every MCP call made by the CLI.
// Saves each pair to ./mcp_capture_<seq>.json and keeps the auth token in ./captured_token.txt
const http = require('http');
const https = require('https');
const zlib = require('zlib');
const fs = require('fs');

const LISTEN_PORT = 8866;
const UPSTREAM_HOST = 'graph.qq.com';
const UPSTREAM_PATH = '/mcp_gateway/open_platform_agent_mcp/mcp';
const OUT_DIR = __dirname;
let seq = 0;
let tokenSaved = false;

const server = http.createServer((req, res) => {
  let reqChunks = [];
  req.on('data', (c) => reqChunks.push(c));
  req.on('end', () => {
    const reqBody = Buffer.concat(reqChunks).toString('utf8');
    const auth = req.headers['authorization'] || '';
    if (!tokenSaved && auth.startsWith('Bearer ')) {
      fs.writeFileSync(OUT_DIR + '/captured_token.txt', auth.replace('Bearer ', '').trim());
      tokenSaved = true;
      console.log('TOKEN SAVED');
    }

    const headers = { ...req.headers };
    delete headers.host;
    delete headers['content-length'];
    headers['Content-Length'] = Buffer.byteLength(reqBody);

    const proxyReq = https.request(
      { host: UPSTREAM_HOST, path: UPSTREAM_PATH, method: req.method, headers },
      (pres) => {
        let resChunks = [];
        pres.on('data', (c) => resChunks.push(c));
        pres.on('end', () => {
          let rawBody = Buffer.concat(resChunks);
          const enc = (pres.headers['content-encoding'] || '').toLowerCase();
          if (enc.includes('gzip')) {
            try { rawBody = zlib.gunzipSync(rawBody); } catch (e) { console.error('gunzip fail: ' + e.message); }
          }
          const resBody = rawBody.toString('utf8');
          const rec = {
            seq: seq,
            time: new Date().toISOString(),
            request: { method: req.method, url: req.url, headers: req.headers, body: reqBody },
            response: { status: pres.statusCode, rawContentEncoding: enc, body: resBody }
          };
          fs.writeFileSync(OUT_DIR + `/mcp_capture_${seq}.json`, JSON.stringify(rec, null, 2));
          console.log(`RECORDED seq=${seq} req=${reqBody.length}B resp=${resBody.length}B`);
          seq++;
          const outHeaders = { 'content-type': 'application/json' };
          res.writeHead(pres.statusCode, outHeaders);
          res.end(resBody);
        });
      }
    );
    proxyReq.on('error', (e) => {
      console.error('proxy error: ' + e.message);
      res.writeHead(502, { 'content-type': 'text/plain' });
      res.end('proxy error: ' + e.message);
    });
    proxyReq.write(reqBody);
    proxyReq.end();
  });
});

server.listen(LISTEN_PORT, '127.0.0.1', () => {
  console.log('mcp capture proxy listening on 127.0.0.1:' + LISTEN_PORT + ' outdir=' + OUT_DIR);
});
