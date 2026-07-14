#!/usr/bin/env node
// 用法: node live-url.js <file.mmd>  → 输出 mermaid.live 的 edit / view 链接
const fs = require('fs');
const zlib = require('zlib');

const code = fs.readFileSync(process.argv[2], 'utf8');
const state = {
  code,
  mermaid: JSON.stringify({ theme: 'default' }),
  autoSync: true,
  rough: false, // 关闭手绘风
  updateDiagram: true,
};
const b64 = zlib
  .deflateSync(Buffer.from(JSON.stringify(state), 'utf8'), { level: 9 })
  .toString('base64url');
console.log('edit: https://mermaid.live/edit#pako:' + b64);
console.log('view: https://mermaid.live/view#pako:' + b64);
