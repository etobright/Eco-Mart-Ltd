(function(root){
 'use strict';
 function quote(lines,promotion){
  const items=lines.map(line=>{
   const subtotal=line.price*line.qty;
   const discount=line.qty>=promotion.quantity?Math.floor((subtotal*promotion.percent+50)/100):0;
   return {id:line.id??null,subtotal,discount,total:subtotal-discount};
  });
  const subtotal=items.reduce((sum,item)=>sum+item.subtotal,0);
  const discount=items.reduce((sum,item)=>sum+item.discount,0);
  return {subtotal,discount,total:subtotal-discount,percent:promotion.percent,quantity:promotion.quantity,scope:'product',items};
 }
 const pricing=Object.freeze({quote});
 if(typeof module!=='undefined'&&module.exports)module.exports=pricing;else root.EcoPricing=pricing;
})(globalThis);
