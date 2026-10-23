"""Automatic bulk discount per product, calculated in integer cents."""
PROMOTION = {'quantity': 6, 'percent': 15, 'scope': 'product'}

def quote(lines):
    items=[]
    for line in lines:
        subtotal=line['price']*line['qty']
        discount=(subtotal*PROMOTION['percent']+50)//100 if line['qty']>=PROMOTION['quantity'] else 0
        items.append({'id':line.get('id'),'subtotal':subtotal,'discount':discount,'total':subtotal-discount})
    subtotal=sum(item['subtotal'] for item in items)
    discount=sum(item['discount'] for item in items)
    return {'subtotal':subtotal,'discount':discount,'total':subtotal-discount,
            'percent':PROMOTION['percent'],'quantity':PROMOTION['quantity'],
            'scope':'product','items':items}
