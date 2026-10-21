const test=require('node:test');
const assert=require('node:assert/strict');
const {normalize,isBarcode}=require('../static/scanner.js');
test('numeric codes and zeros survive keyboard and suffix normalization',()=>{
 for(const code of ['2001948374145','012345678901','00012345','12345678901234']){
  assert.equal(normalize(code+'\r\n'),code);assert.ok(isBarcode(normalize(code)));
 }
 assert.equal(normalize('２００１９４８３７４１４５'),'2001948374145');
 assert.equal(normalize(']E02001948374145'),'2001948374145');
});
test('French and Belgian AZERTY scans map back to their original digits',()=>{
 const code='2001948374145',fr='à&é"\'( -è_ç'.replace(' ',''),be='à&é"\'(§è!ç';
 for(const keyboard of [fr,be]){
  const raw=[...code].map(c=>keyboard[+c]).join('');
  assert.equal(normalize(raw),code);assert.ok(isBarcode(normalize(raw)));
 }
 assert.equal(normalize('ÉÀÀ&Ç(_"è(&(\''),'2001958375154');
});
test('unsupported scanner data is not silently reduced to a product number',()=>{
 for(const raw of ['ABC2001948374145','https://example.com/2001948374145','200194x8374145']){
  assert.equal(normalize(raw),raw);assert.equal(isBarcode(normalize(raw)),false);
 }
 assert.equal(isBarcode(normalize('123')),false);
});
