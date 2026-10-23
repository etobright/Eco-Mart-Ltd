const test=require('node:test'),assert=require('node:assert/strict');
const {quote}=require('../static/pricing.js');
const promotion={quantity:6,percent:15,scope:'product'};
test('the sixth identical item enables one discount, removed below six',()=>{
 assert.equal(quote([{price:10000,qty:5}],promotion).total,50000);
 assert.equal(quote([{price:10000,qty:6}],promotion).total,51000);
 assert.equal(quote([{price:10000,qty:7}],promotion).total,59500);
 assert.equal(quote([{price:10000,qty:12}],promotion).total,102000);
 assert.equal(quote([{price:10000,qty:3},{price:10000,qty:3}],promotion).discount,0);
});
test('mixed baskets discount only qualifying products without compounding',()=>{
 const lines=[{price:10000,qty:6},{price:20000,qty:1}];
 assert.equal(quote(lines,promotion).total,71000);
 assert.equal(quote(lines,promotion).items[1].discount,0);
 assert.equal(quote([{price:10000,qty:6},{price:20000,qty:6}],promotion).discount,27000);
 assert.equal(quote([{price:1,qty:10}],promotion).discount,2);
});
