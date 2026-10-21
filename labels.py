"""Vector EAN-13 labels with an exact 50 × 25 mm PDF page size."""
MM = 72 / 25.4
L = ('0001101','0011001','0010011','0111101','0100011','0110001','0101111','0111011','0110111','0001011')
G = ('0100111','0110011','0011011','0100001','0011101','0111001','0000101','0010001','0001001','0010111')
PARITY = ('LLLLLL','LLGLGG','LLGGLG','LLGGGL','LGLLGG','LGGLLG','LGGGLL','LGLGLG','LGLGGL','LGGLGL')

def ean_bits(code):
    if len(code) != 13 or not code.isascii() or not code.isdigit():
        raise ValueError('Les étiquettes utilisent un code EAN-13.')
    if (-sum(int(c)*(1 if i%2==0 else 3) for i,c in enumerate(code[:12])))%10 != int(code[-1]):
        raise ValueError('Clé EAN-13 invalide.')
    left = ''.join((L if parity=='L' else G)[int(c)] for c,parity in zip(code[1:7], PARITY[int(code[0])]))
    right = ''.join(''.join('1' if bit=='0' else '0' for bit in L[int(c)]) for c in code[7:])
    return '101' + left + '01010' + right + '101'

def label_pdf(product, count):
    if not 1 <= count <= 200: raise ValueError('Choisissez entre 1 et 200 étiquettes.')
    code = product['barcode']
    bits = ean_bits(code)
    width, height = 50*MM, 25*MM
    # One reusable content stream for all pages; no scripts or remote resources.
    commands = ['0 g']
    def text(value, size, baseline, font='F1'):
        data = str(value).encode('cp1252', errors='replace')
        # Center text in a fixed-width font and reduce long names to fit.
        size = min(size, (46*MM)/(max(1,len(data))*.6))
        x = (width-len(data)*size*.6)/2
        commands.append(f'BT /{font} {size:.4f} Tf {x:.4f} {baseline*MM:.4f} Td <{data.hex()}> Tj ET')
    name = product['name']
    if len(name)>45: name=name[:42]+'...'
    text(name, 7, 21.6, 'F2')
    module = 46*MM / 117
    for i,bit in enumerate(bits):
        if bit=='1':
            guard = i<3 or i>=92 or 45<=i<50
            commands.append(f'{2*MM+(i+11)*module:.5f} {8.3*MM:.5f} {module:.5f} {(12.3 if guard else 11.3)*MM:.5f} re f')
    text(code,7,5.4)
    text(f"Rs {product['price']/100:,.2f}".replace(',',' ').replace('.',','),10,1.3,'F2')
    stream = '\n'.join(commands).encode('ascii')
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>', b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier-Bold /Encoding /WinAnsiEncoding >>', f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream']
    kids=[]
    for _ in range(count):
        oid=len(objects)+1;kids.append(f'{oid} 0 R')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:.6f} {height:.6f}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents 5 0 R >>'.encode())
    objects[1]=f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {count} >>".encode()
    output=bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');offsets=[0]
    for oid,obj in enumerate(objects,1):
        offsets.append(len(output));output.extend(f'{oid} 0 obj\n'.encode()+obj+b'\nendobj\n')
    xref=len(output);output.extend(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode())
    for offset in offsets[1:]:output.extend(f'{offset:010d} 00000 n \n'.encode())
    output.extend(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return bytes(output)
