from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from models import db, Inscricao, ParcelaPagamento, Produto
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import random
import string

bp = Blueprint('main', __name__)

def crc16(data: str) -> str:
    polynomial = 0x1021
    crc = 0xFFFF
    for byte in data.encode('utf-8'):
        crc ^= (byte << 8)
        for _ in range(8):
            if (crc & 0x8000):
                crc = (crc << 1) ^ polynomial
            else:
                crc = (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"

def generate_pix(amount: float) -> str:
    key = "0a3f0867-d2ab-42f7-b209-4ad24deeeb03"
    name = "FUNDACAO ALBERTINA BRITO"[:25] # max 25 chars
    city = "BRASILIA"[:15] # max 15 chars
    txid = "***"
    
    payloadFormat = "000201"
    merchantAccount = f"0014br.gov.bcb.pix01{len(key):02d}{key}"
    merchantAccountInfo = f"26{len(merchantAccount):02d}{merchantAccount}"
    merchantCategoryCode = "52040000"
    transactionCurrency = "5303986"
    transactionAmount = f"{amount:.2f}"
    transactionAmountField = f"54{len(transactionAmount):02d}{transactionAmount}"
    countryCode = "5802BR"
    merchantName = f"59{len(name):02d}{name}"
    merchantCity = f"60{len(city):02d}{city}"
    additionalDataFieldTemplate = f"05{len(txid):02d}{txid}"
    additionalData = f"62{len(additionalDataFieldTemplate):02d}{additionalDataFieldTemplate}"

    payload = f"{payloadFormat}{merchantAccountInfo}{merchantCategoryCode}{transactionCurrency}{transactionAmountField}{countryCode}{merchantName}{merchantCity}{additionalData}6304"
    crc = crc16(payload)
    return payload + crc

def get_max_parcelas():
    # O evento é em Novembro.
    # Maio: até 6x (Maio, Jun, Jul, Ago, Set, Out)
    hoje = date.today()
    mes_evento = 11
    ano_evento = 2026
    
    if hoje.year > ano_evento or (hoje.year == ano_evento and hoje.month >= mes_evento):
        return 1
        
    meses_diferenca = (ano_evento - hoje.year) * 12 + (mes_evento - hoje.month)
    return max(1, meses_diferenca)

@bp.route('/')
def home():
    max_parcelas = get_max_parcelas()
    meses_disponiveis = list(range(1, max_parcelas + 1))
    produtos = Produto.query.all()
    return render_template('home.html', produtos=produtos, meses_disponiveis=meses_disponiveis)

@bp.route('/inscrever', methods=['POST'])
def inscrever():
    tipo_inscricao = request.form.get('tipo_inscricao')
    nome_completo = request.form.get('nome_completo')
    nome_conjuge = request.form.get('nome_conjuge')
    telefone = request.form.get('telefone')
    data_casamento_str = request.form.get('data_casamento')
    local_congregacao = request.form.get('local_congregacao')
    cpf_responsavel = request.form.get('cpf_responsavel')
    qtd_parcelas = int(request.form.get('parcelas', 1))
    dia_vencimento = int(request.form.get('dia_vencimento', 10))

    try:
        data_casamento = datetime.strptime(data_casamento_str, '%Y-%m-%d').date()
    except:
        data_casamento = date.today()

    produto = Produto.query.filter_by(identificador=tipo_inscricao).first()
    if not produto or produto.vagas_disponiveis <= 0:
        return "Desculpe, as vagas para esta opção estão esgotadas.", 400

    produto.vagas_ocupadas += 1

    nova_inscricao = Inscricao(
        tipo_inscricao=produto.nome, # Salva o nome real
        nome_completo=nome_completo,
        nome_conjuge=nome_conjuge,
        telefone=telefone,
        data_casamento=data_casamento,
        local_congregacao=local_congregacao,
        cpf_responsavel=cpf_responsavel if tipo_inscricao == 'jantar_hotel' else None
    )
    
    db.session.add(nova_inscricao)
    db.session.commit()

    valor_total = produto.valor
    valor_parcela = round(valor_total / qtd_parcelas, 2)

    hoje = date.today()
    for i in range(qtd_parcelas):
        mes_vencimento = hoje.month + i
        ano_vencimento = hoje.year
        
        while mes_vencimento > 12:
            mes_vencimento -= 12
            ano_vencimento += 1
        
        try:
            data_venc = date(ano_vencimento, mes_vencimento, dia_vencimento)
        except ValueError:
            # Caso dia inválido (ex: 30 de fev), pega o primeiro dia do próximo mês e volta 1 dia
            prox_mes = mes_vencimento + 1
            ano_prox = ano_vencimento
            if prox_mes > 12:
                prox_mes = 1
                ano_prox += 1
            data_venc = date(ano_prox, prox_mes, 1) - relativedelta(days=1)

        nova_parcela = ParcelaPagamento(
            inscricao_id=nova_inscricao.id,
            numero_parcela=i+1,
            valor_parcela=valor_parcela,
            data_vencimento=data_venc,
            chave_pix_copia_cola=generate_pix(valor_parcela)
        )
        db.session.add(nova_parcela)
    
    db.session.commit()

    try:
        from whatsapp import send_message
        msg = f"Olá, *{nome_completo}*!\n\nRecebemos a solicitação de inscrição para o *Jantar de Casais DEFAD*.\n\n"
        msg += f"Inscrição: {tipo_inscricao.replace('_', ' + ').title()}\n"
        msg += f"Valor Total: R$ {valor_total:.2f}\n\n"
        
        if qtd_parcelas == 1:
            msg += f"Pagamento: À vista (1x de R$ {valor_parcela:.2f})\n"
        else:
            msg += f"Pagamento: Parcelado em {qtd_parcelas}x de R$ {valor_parcela:.2f}\n"
            
        msg += "\n*Importante:* A sua inscrição só será de fato efetivada quando realizar o pagamento por completo.\n\n"
        msg += "Verifique a tela do site para realizar o pagamento, ou aguarde nossas cobranças com o PIX Copia e Cola!"
        
        send_message(telefone, msg)
    except Exception as e:
        print("Erro ao enviar WhatsApp de Solicitação:", e)

    return redirect(url_for('main.checkout', id=nova_inscricao.id))

@bp.route('/checkout/<int:id>')
def checkout(id):
    inscricao = Inscricao.query.get_or_404(id)
    return render_template('checkout.html', inscricao=inscricao)

@bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('main.admin'))
        else:
            flash('Senha incorreta!', 'error')
    return render_template('login.html')

@bp.route('/admin_logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('main.home'))

@bp.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))
    
    inscricoes = Inscricao.query.order_by(Inscricao.data_inscricao.desc()).all()
    produtos = Produto.query.all()
    
    total_inscritos = len(inscricoes)
    
    parcelas_pagas = ParcelaPagamento.query.filter_by(status_parcela='Pago').all()
    valor_arrecadado = sum(p.valor_parcela for p in parcelas_pagas)
    
    parcelas_pendentes = ParcelaPagamento.query.filter_by(status_parcela='Pendente').all()
    valor_a_receber = sum(p.valor_parcela for p in parcelas_pendentes)
    
    return render_template('admin.html', 
                           inscricoes=inscricoes, 
                           produtos=produtos,
                           total_inscritos=total_inscritos,
                           valor_arrecadado=valor_arrecadado,
                           valor_a_receber=valor_a_receber)

@bp.route('/admin/produto/editar/<int:id>', methods=['POST'])
def editar_produto(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))
    
    produto = Produto.query.get_or_404(id)
    produto.nome = request.form.get('nome')
    produto.valor = float(request.form.get('valor'))
    produto.vagas_totais = int(request.form.get('vagas_totais'))
    
    db.session.commit()
    flash(f'Produto {produto.nome} atualizado com sucesso!', 'success')
    return redirect(url_for('main.admin'))

@bp.route('/admin/pagar_parcela/<int:id>', methods=['POST'])
def pagar_parcela(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))
    
    parcela = ParcelaPagamento.query.get_or_404(id)
    parcela.status_parcela = 'Pago'
    
    inscricao = parcela.inscricao
    todas_parcelas = inscricao.parcelas
    pagas = [p for p in todas_parcelas if p.status_parcela == 'Pago']
    
    if len(pagas) == len(todas_parcelas):
        inscricao.status_geral = 'Pago Total'
        try:
            from whatsapp import send_message
            msg_comprovante = f"🎉 *COMPROVANTE DE INSCRIÇÃO REALIZADA* 🎉\n\nOlá, {inscricao.nome_completo}!\nO pagamento total da sua inscrição no Jantar de Casais DEFAD foi confirmado!\nSua vaga está garantida. Nos vemos lá!"
            send_message(inscricao.telefone, msg_comprovante)
        except Exception as e:
            print("Erro ao enviar Comprovante WhatsApp:", e)
            
    elif len(pagas) > 0:
        inscricao.status_geral = 'Pago Parcial'
        
    db.session.commit()
    
    flash(f'Parcela {parcela.numero_parcela} de {inscricao.nome_completo} confirmada!', 'success')
    return redirect(url_for('main.admin'))

@bp.route('/admin/exportar_pdf')
def exportar_pdf():
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))
        
    try:
        from fpdf import FPDF
    except ImportError:
        flash("Biblioteca fpdf2 não está instalada.", "error")
        return redirect(url_for('main.admin'))

    inscricoes = Inscricao.query.order_by(Inscricao.data_inscricao.desc()).all()

    class PDF(FPDF):
        def header(self):
            self.set_font("helvetica", "B", 15)
            self.cell(0, 10, "Relatório de Inscritos - Jantar de Casais DEFAD", new_x="LMARGIN", new_y="NEXT", align="C")
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font("helvetica", "I", 8)
            self.cell(0, 10, f"Página {self.page_no()}/{{nb}}", align="C")

    pdf = PDF(orientation="L", format="A4")
    pdf.add_page()
    pdf.set_font("helvetica", "B", 10)
    
    # Header da tabela
    col_widths = [15, 60, 60, 35, 40, 25, 30] # total 265 (~270 A4 Landscape)
    headers = ["ID", "Casal", "Congregação", "WhatsApp", "Tipo", "Data Cas.", "Status"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 10, h, border=1, align="C")
    pdf.ln()

    # Linhas
    pdf.set_font("helvetica", "", 9)
    fill = False
    pdf.set_fill_color(240, 240, 240)
    
    for ins in inscricoes:
        casal = f"{ins.nome_completo} & {ins.nome_conjuge}"
        # Cortar textos longos se necessário
        if len(casal) > 40: casal = casal[:37] + "..."
        congreg = ins.local_congregacao
        if len(congreg) > 35: congreg = congreg[:32] + "..."
        
        pdf.cell(col_widths[0], 8, str(ins.id), border=1, align="C", fill=fill)
        pdf.cell(col_widths[1], 8, casal, border=1, fill=fill)
        pdf.cell(col_widths[2], 8, congreg, border=1, fill=fill)
        pdf.cell(col_widths[3], 8, ins.telefone, border=1, align="C", fill=fill)
        pdf.cell(col_widths[4], 8, ins.tipo_inscricao[:20], border=1, align="C", fill=fill)
        pdf.cell(col_widths[5], 8, ins.data_casamento.strftime("%d/%m/%Y"), border=1, align="C", fill=fill)
        pdf.cell(col_widths[6], 8, ins.status_geral, border=1, align="C", fill=fill)
        pdf.ln()
        fill = not fill

    from flask import send_file
    import io
    pdf_bytes = pdf.output(dest='S')
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name='relatorio_inscritos.pdf'
    )

@bp.route('/admin/excluir_inscricao/<int:id>', methods=['POST'])
def excluir_inscricao(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('main.admin_login'))
        
    inscricao = Inscricao.query.get_or_404(id)
    
    # Devolver vaga pro estoque
    produto = Produto.query.filter_by(nome=inscricao.tipo_inscricao).first()
    if produto and produto.vagas_ocupadas > 0:
        produto.vagas_ocupadas -= 1
        
    db.session.delete(inscricao)
    db.session.commit()
    
    flash(f"Inscrição de {inscricao.nome_completo} excluída com sucesso. A vaga foi devolvida ao estoque.", "success")
    return redirect(url_for('main.admin'))
