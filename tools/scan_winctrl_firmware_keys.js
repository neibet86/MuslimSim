/* Read-only search for a SimAppPro AES firmware key in its native modules.

   The cached MCDU/PFP files have a 14-byte clear header followed by an
   AES-block-sized body.  Repeated ciphertext blocks are likely erased flash
   (all 00 or all FF).  Trying native-module byte windows as keys against that
   known plaintext is a small, deterministic check; no device is opened.
*/

'use strict';

const crypto = require('crypto');
const fs = require('fs');

const firmwarePath =
  'C:\\Users\\noureddine aidoudi\\AppData\\Roaming\\SimAppPro\\Download\\Firmware\\MCDU-32';
const nativePaths = [
  'C:\\Program Files (x86)\\SimAppPro\\resources\\app.asar.unpacked\\WWTHID_JSAPI.node',
  'C:\\Program Files (x86)\\SimAppPro\\resources\\app.asar.unpacked\\WWTHID.dll',
];

function decryptBlock(ciphertext, key) {
  const algorithm = `aes-${key.length * 8}-ecb`;
  const decipher = crypto.createDecipheriv(algorithm, key, null);
  decipher.setAutoPadding(false);
  return Buffer.concat([decipher.update(ciphertext), decipher.final()]);
}

function uniform(buffer, value) {
  return buffer.every(byte => byte === value);
}

function main() {
  const firmware = fs.readFileSync(firmwarePath);
  const encrypted = firmware.subarray(14);
  if (encrypted.length % 16 !== 0) {
    throw new Error('Firmware body is not aligned after the 14-byte header');
  }

  const counts = new Map();
  for (let offset = 0; offset < encrypted.length; offset += 16) {
    const hex = encrypted.subarray(offset, offset + 16).toString('hex');
    counts.set(hex, (counts.get(hex) || 0) + 1);
  }
  const [targetHex, targetCount] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0];
  const target = Buffer.from(targetHex, 'hex');
  const first = encrypted.subarray(0, 16);
  console.log(`most repeated block: ${targetHex} x ${targetCount}`);

  let tested = 0;
  let matches = 0;
  for (const path of nativePaths) {
    const data = fs.readFileSync(path);
    for (const keyLength of [16, 24, 32]) {
      // Constants are normally naturally aligned.  This first pass keeps the
      // experiment quick; use --all-offsets only if it finds nothing.
      const step = process.argv.includes('--all-offsets') ? 1 : 4;
      for (let offset = 0; offset + keyLength <= data.length; offset += step) {
        const key = data.subarray(offset, offset + keyLength);
        let plain;
        try {
          plain = decryptBlock(target, key);
        } catch (_error) {
          continue;
        }
        tested += 1;
        if (!uniform(plain, 0x00) && !uniform(plain, 0xFF)) {
          continue;
        }
        const firstPlain = decryptBlock(first, key);
        console.log(
          `MATCH ${path} offset=0x${offset.toString(16)} ` +
          `AES-${keyLength * 8} key=${key.toString('hex')} ` +
          `repeatPlain=${plain.toString('hex')} firstPlain=${firstPlain.toString('hex')}`
        );
        matches += 1;
      }
    }
  }
  console.log(`tested ${tested} candidate keys; matches ${matches}`);
}

main();
