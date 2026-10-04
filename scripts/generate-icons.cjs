const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

// CRC32 table and calculation for PNG chunks
const crcTable = [];
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) {
    c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  }
  crcTable[n] = c;
}

function crc32(buf) {
  let crc = 0xffffffff;
  for (let i = 0; i < buf.length; i++) {
    crc = crcTable[(crc ^ buf[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function createChunk(type, data) {
  const typeBuf = Buffer.from(type, 'ascii');
  const lenBuf = Buffer.alloc(4);
  lenBuf.writeUInt32BE(data.length, 0);

  const crcBuf = Buffer.alloc(4);
  const toCrc = Buffer.concat([typeBuf, data]);
  crcBuf.writeUInt32BE(crc32(toCrc), 0);

  return Buffer.concat([lenBuf, typeBuf, data, crcBuf]);
}

function createPng(width, height, r = 79, g = 70, b = 229) { // default Indigo
  const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);

  // IHDR: width(4), height(4), bitDepth(1)=8, colorType(1)=6(RGBA), comp(1)=0, filter(1)=0, interlace(1)=0
  const ihdrData = Buffer.alloc(13);
  ihdrData.writeUInt32BE(width, 0);
  ihdrData.writeUInt32BE(height, 4);
  ihdrData.writeUInt8(8, 8); // bit depth 8
  ihdrData.writeUInt8(6, 9); // RGBA
  ihdrData.writeUInt8(0, 10);
  ihdrData.writeUInt8(0, 11);
  ihdrData.writeUInt8(0, 12);
  const ihdrChunk = createChunk('IHDR', ihdrData);

  // Uncompressed raw scanlines: each line begins with filter byte (0), then width * 4 bytes
  const scanlines = Buffer.alloc(height * (1 + width * 4));
  let offset = 0;
  for (let y = 0; y < height; y++) {
    scanlines[offset++] = 0; // Filter: none
    for (let x = 0; x < width; x++) {
      // Create a nice gradient with border effect
      const border = 2;
      const isBorder = x < border || x >= width - border || y < border || y >= height - border;
      if (isBorder) {
        scanlines[offset++] = 99; // R
        scanlines[offset++] = 102; // G
        scanlines[offset++] = 241; // B (indigo-500)
        scanlines[offset++] = 255; // A
      } else {
        scanlines[offset++] = r;
        scanlines[offset++] = g;
        scanlines[offset++] = b;
        scanlines[offset++] = 255;
      }
    }
  }

  const compressedData = zlib.deflateSync(scanlines);
  const idatChunk = createChunk('IDAT', compressedData);
  const iendChunk = createChunk('IEND', Buffer.alloc(0));

  return Buffer.concat([signature, ihdrChunk, idatChunk, iendChunk]);
}

const iconsDir = path.join(__dirname, '..', 'src-tauri', 'icons');
if (!fs.existsSync(iconsDir)) {
  fs.mkdirSync(iconsDir, { recursive: true });
}

// Generate standard PNG sizes
fs.writeFileSync(path.join(iconsDir, '32x32.png'), createPng(32, 32));
fs.writeFileSync(path.join(iconsDir, '128x128.png'), createPng(128, 128));
fs.writeFileSync(path.join(iconsDir, '128x128@2x.png'), createPng(256, 256));
fs.writeFileSync(path.join(iconsDir, 'icon.png'), createPng(512, 512));

// For ico and icns in dev, minimal dummy icon container or copy valid png
// (Tauri CLI will use `npm run tauri icon` if a custom source is given, but having these files satisfies bundle.icon)
fs.writeFileSync(path.join(iconsDir, 'icon.ico'), createPng(32, 32));
fs.writeFileSync(path.join(iconsDir, 'icon.icns'), createPng(128, 128));

console.log('App icons generated successfully in src-tauri/icons/');
