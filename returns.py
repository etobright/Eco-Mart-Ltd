"""Refund allocation against immutable sale snapshots, in integer cents."""
import json

def portion(total, quantity, returned):
    return (2*total*returned+quantity)//(2*quantity) if quantity else 0

def sale_items(sale):
    lines=json.loads(sale['lines'])
    pricing=json.loads(sale['pricing'] or '{}')
    priced=pricing.get('items',[])
    paid=[priced[i]['total'] if i<len(priced) else line['qty']*line['price'] for i,line in enumerate(lines)]
    if sum(paid)!=sale['total']: raise ValueError('Les montants de ce ticket sont incohérents. Aucun remboursement enregistré.')
    return lines,paid

def returned_quantities(records, size):
    quantities=[0]*size
    for record in records:
        for item in json.loads(record['lines']): quantities[item['line_index']]+=item['qty']
    return quantities

def prepare(sale, records, requested):
    lines,paid=sale_items(sale)
    returned=returned_quantities(records,len(lines))
    if not isinstance(requested,list) or not requested: raise ValueError('Sélectionnez au moins un article à retourner.')
    items=[];seen=set()
    for item in requested:
        if not isinstance(item,dict): raise ValueError('Article de retour invalide.')
        index=item.get('line_index');qty=item.get('qty');restock=item.get('restock')
        if type(index) is not int or not 0<=index<len(lines) or index in seen: raise ValueError('Ligne de ticket invalide ou dupliquée.')
        seen.add(index);line=lines[index];before=returned[index]
        if type(qty) is not int or not 1<=qty<=line['qty']-before: raise ValueError('Quantité supérieure au nombre d’articles encore retournables.')
        if type(restock) is not bool: raise ValueError('Précisez si le produit doit revenir en stock.')
        amount=portion(paid[index],line['qty'],before+qty)-portion(paid[index],line['qty'],before)
        items.append({'line_index':index,'product_id':line['id'],'name':line['name'],'barcode':line.get('barcode',''),'qty':qty,'amount':amount,'restock_requested':restock})
        returned[index]+=qty
    total=sum(item['amount'] for item in items)
    prior_total=sum(record['total'] for record in records)
    if prior_total+total>sale['total']: raise ValueError('Le remboursement dépasse le montant payé.')
    tax=portion(sale['tax'],sale['total'],prior_total+total)-portion(sale['tax'],sale['total'],prior_total)
    return items,total,tax,all(q==line['qty'] for q,line in zip(returned,lines))
