from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    identificador = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    vagas_totais = db.Column(db.Integer, nullable=False)
    vagas_ocupadas = db.Column(db.Integer, default=0)

    @property
    def vagas_disponiveis(self):
        return max(0, self.vagas_totais - self.vagas_ocupadas)

class Inscricao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo_inscricao = db.Column(db.String(50), nullable=False) # 'jantar' ou 'jantar_hotel'
    nome_completo = db.Column(db.String(100), nullable=False)
    nome_conjuge = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20), nullable=False)
    data_casamento = db.Column(db.Date, nullable=False)
    local_congregacao = db.Column(db.String(100), nullable=False)
    cpf_responsavel = db.Column(db.String(20), nullable=True)
    status_geral = db.Column(db.String(50), default='Pendente') # 'Pendente', 'Pago Parcial', 'Pago Total'
    data_inscricao = db.Column(db.DateTime, default=datetime.utcnow)

    parcelas = db.relationship('ParcelaPagamento', backref='inscricao', lazy=True, cascade="all, delete-orphan")

class ParcelaPagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inscricao_id = db.Column(db.Integer, db.ForeignKey('inscricao.id'), nullable=False)
    numero_parcela = db.Column(db.Integer, nullable=False)
    valor_parcela = db.Column(db.Float, nullable=False)
    data_vencimento = db.Column(db.Date, nullable=False)
    status_parcela = db.Column(db.String(50), default='Pendente') # 'Pendente' ou 'Pago'
    chave_pix_copia_cola = db.Column(db.Text, nullable=True)
