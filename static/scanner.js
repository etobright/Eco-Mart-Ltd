/* USB keyboard scanners can type French/Belgian top-row symbols on AZERTY. */
(function (root) {
  'use strict';
  const azertyDigits = {
    '&': '1', 'é': '2', '"': '3', "'": '4', '(': '5', '-': '6',
    'è': '7', '_': '8', 'ç': '9', 'à': '0', '§': '6', '!': '8',
    'É': '2', 'È': '7', 'Ç': '9', 'À': '0',
  };
  function normalize(value) {
    let code = String(value ?? '').normalize('NFKC')
      .replace(/[\r\n\t\u200b-\u200d\ufeff]/g, '').trim();
    // AIM identifiers added by some EAN/UPC readers; never remove arbitrary letters.
    code = code.replace(/^\]E[04]/, '');
    const characters = [...code];
    if (characters.every(c => /[0-9]/.test(c) || Object.hasOwn(azertyDigits, c))) {
      code = characters.map(c => azertyDigits[c] ?? c).join('');
    }
    return code;
  }
  function isBarcode(value) { return /^(?:\d{8}|\d{12,14})$/.test(value); }
  const scanner = Object.freeze({ normalize, isBarcode });
  if (typeof module !== 'undefined' && module.exports) module.exports = scanner;
  else root.EcoScanner = scanner;
})(globalThis);
