from flask import Flask, render_template, request, jsonify, abort
from werkzeug.utils import secure_filename
import pandas as pd
import os
import logging
from datetime import datetime
import hashlib
import re

app = Flask(__name__)
# Configure logging
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')

ALLOWED_EXTENSIONS = {'csv', 'xlsx'}
REQUIRED_COLUMNS = ['date', 'description', 'amount']

# Nubank specific column mappings
COLUMN_MAPPINGS = {
    'date': ['Data', 'data'],
    'description': ['Descrição', 'descricao', 'descrição'],
    'amount': ['Valor', 'valor'],
    'id': ['Identificador', 'identificador']
}

class ValidationError(Exception):
    pass

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def map_nubank_columns(df):
    """Map Nubank specific column names"""
    try:
        print("Starting column mapping...")
        print("Original columns:", df.columns.tolist())
        
        # Create a copy to avoid modifying the original
        df = df.copy()
        
        # Simple direct mapping without encoding conversion
        mapped_columns = {}
        for standard_name, variations in COLUMN_MAPPINGS.items():
            for col in df.columns:
                if col in variations:
                    mapped_columns[col] = standard_name
                    print(f"Mapping column {col} to {standard_name}")
                    break
        
        if mapped_columns:
            df = df.rename(columns=mapped_columns)
            print("Mapped columns:", df.columns.tolist())
        else:
            print("No columns were mapped!")
        
        return df
        
    except Exception as e:
        print(f"Error in map_nubank_columns: {str(e)}")
        raise

def process_nubank_data(df):
    """Process Nubank specific data format"""
    try:
        print("Starting data processing...")
        df = df.copy()
        
        # Convert date format
        print("Converting dates...")
        df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y')
        
        # Convert amount to float
        print("Converting amounts...")
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        
        # Categorize transactions
        print("Categorizing transactions...")
        df['category'] = df['description'].apply(categorize_transaction)
        
        print("Data processing completed")
        return df
        
    except Exception as e:
        print(f"Error in process_nubank_data: {str(e)}")
        raise

def simplify_description(description):
    """Simplify transaction descriptions by extracting the main recipient name"""
    # Convert to lowercase for consistent matching
    desc = description.lower()
    
    # Remove common prefixes and suffixes
    prefixes_to_remove = [
        'pagamento em ', 'compra em ', 'compra com cartao ', 
        'compra cartao ', 'compra ', 'pgto ', 'pag ', 'pagto ',
        'transferência enviada pelo pix - ', 'transferência recebida pelo pix - ',
        'transferência enviada - ', 'transferência recebida - ',
        'pagamento da fatura - ', 'pagamento fatura - '
    ]
    
    for prefix in prefixes_to_remove:
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
    
    # Split by common separators and take the first part
    desc = desc.split(' - ')[0]
    desc = desc.split('ltda')[0]
    desc = desc.split('s.a.')[0]
    desc = desc.split('s/a')[0]
    
    # Clean up the result
    desc = desc.strip()
    # Capitalize each word
    desc = ' '.join(word.capitalize() for word in desc.split())
    
    return desc

def categorize_transaction(description):
    """Categorize Nubank transactions based on description"""
    description = description.lower().strip()
    
    categories = {
        'contas': [
            'energia', 'água', 'gas natural', 'internet', 'fibra',
            'condomínio', 'aluguel', 'iptu', 'taxa', 'copasa',
            'cemig', 'comgas', 'fatura', 'fgts', 'seguro',
            'financiamento', 'prestação', 'parcela fixa'
        ],
        
        'restaurantes': [
            'restaurante', 'rest ', 'bar', 'food', 'ifood',
            'lanchonete', 'padaria', 'cafeteria', 'pizzaria',
            'hamburger', 'açaí', 'doceria', 'confeitaria',
            'churrascaria', 'sushi', 'china', 'mc donalds',
            'burger king', 'subway', 'habib', 'spoleto',
            'giraffas', 'outback', 'starbucks', 'kfc'
        ],
        
        'mercado': [
            'mercado', 'supermercado', 'hortifruti', 'mercearia',
            'atacadão', 'atacadista', 'feira', 'sacolão',
            'carrefour', 'pão de açúcar', 'extra', 'dia',
            'assaí', 'sams club', 'makro', 'quitanda',
            'açougue', 'peixaria', 'hortifruti', 'natural'
        ],
        
        'compras': [
            'shopping', 'loja', 'store', 'magazine', 'varejo',
            'americanas', 'renner', 'riachuelo', 'c&a', 'zara',
            'nike', 'adidas', 'amazon', 'mercado livre', 'aliexpress',
            'shopee', 'magalu', 'casas bahia', 'ponto frio',
            'marisa', 'centauro', 'decathlon'
        ],
        
        'transporte': [
            'uber', '99taxi', '99 pop', 'taxi', 'cabify',
            'combustível', 'gasolina', 'etanol', 'alcool',
            'posto', 'shell', 'ipiranga', 'br ', 'petrobras',
            'estacionamento', 'zona azul', 'pedágio', 'sem parar',
            'conectcar', 'move', 'veloe', 'bilhete', 'metrô',
            'metro', 'cptm', 'sptrans', 'brt', 'van', 'trem'
        ],
        
        'saúde': [
            'drogaria', 'farmacia', 'farmácia', 'hospital',
            'clínica', 'consultório', 'médico', 'dentista',
            'laboratório', 'exame', 'academia', 'psicólogo',
            'fisioterapia', 'nutricionista', 'droga raia',
            'drogasil', 'pacheco', 'ultrafarma', 'pague menos',
            'smart fit', 'bio ritmo'
        ],
        
        'lazer': [
            'cinema', 'teatro', 'show', 'evento', 'ingresso',
            'netflix', 'spotify', 'disney', 'hbo', 'prime',
            'youtube', 'jogos', 'games', 'steam', 'playstation',
            'xbox', 'bilheteria', 'festa', 'boate', 'bar',
            'parque', 'museu', 'livraria', 'cultura'
        ],
        
        'educação': [
            'escola', 'faculdade', 'universidade', 'curso',
            'livro', 'material escolar', 'mensalidade',
            'matrícula', 'udemy', 'coursera', 'alura',
            'kultivi', 'duolingo', 'babbel', 'rosetta'
        ],
        
        'transferências': [
            'transferência', 'pix', 'ted', 'doc',
            'transferencia enviada', 'transferência enviada',
            'envio pix', 'pagamento'
        ]
    }
    
    # First, try exact matches
    for category, keywords in categories.items():
        if any(keyword == description for keyword in keywords):
            return category
            
    # Then try partial matches
    for category, keywords in categories.items():
        if any(keyword in description for keyword in keywords):
            return category
    
    # Check for specific patterns in the description
    if 'pix' in description and ('enviado' in description or 'enviada' in description):
        return 'transferências'
    if 'transferência' in description and ('enviado' in description or 'enviada' in description):
        return 'transferências'
    
    # If no match is found
    return 'outros'

def sanitize_dataframe(df):
    # Convert column names to lowercase
    df.columns = df.columns.str.lower()
    
    # Remove any potentially dangerous characters from string columns
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].apply(lambda x: re.sub(r'[<>{}]', '', str(x)))
    
    return df

def secure_file_storage(file):
    # Generate unique filename using timestamp and hash
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    content_hash = hashlib.md5(file.read()).hexdigest()[:10]
    file.seek(0)  # Reset file pointer after reading
    
    filename = secure_filename(f"{timestamp}_{content_hash}_{file.filename}")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    return filepath

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File is too large (max 16MB)'}), 413

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            raise ValidationError('No file part')
        
        file = request.files['file']
        if file.filename == '':
            raise ValidationError('No selected file')
        
        if not allowed_file(file.filename):
            raise ValidationError('Invalid file type. Please upload CSV or XLSX files only.')
        
        filepath = secure_file_storage(file)
        file.save(filepath)
        
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
            df = None
            
            for encoding in encodings:
                try:
                    print(f"Trying to read file with {encoding} encoding...")
                    df = pd.read_csv(filepath, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e:
                    print(f"Error with {encoding} encoding: {str(e)}")
                    continue
            
            if df is None:
                raise ValidationError("Could not read the file with any supported encoding")
            
            print("Original columns:", df.columns.tolist())
            print("Sample data:", df.head().to_dict())
            
            # Map Nubank columns and process data
            df = map_nubank_columns(df)
            print("After mapping columns:", df.columns.tolist())
            
            df = process_nubank_data(df)
            print("After processing data:", df.head().to_dict())
            
            # Analyze transactions
            analysis_results = analyze_transactions(df)
            
            # Clean up
            os.remove(filepath)
            
            return jsonify(analysis_results)
            
        except Exception as e:
            if os.path.exists(filepath):
                os.remove(filepath)
            print(f"Error processing file: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise
            
    except ValidationError as e:
        logging.warning(f"Validation error: {str(e)}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

def analyze_transactions(df):
    """Analyze Nubank transactions"""
    try:
        print("Starting transaction analysis...")
        
        # Basic statistics
        total_spent = float(df[df['amount'] < 0]['amount'].sum())
        total_received = float(df[df['amount'] > 0]['amount'].sum())
        
        print(f"Total spent: {total_spent}")
        print(f"Total received: {total_received}")
        
        # Category analysis
        category_spending = df[df['amount'] < 0].groupby('category')['amount'].sum().abs().round(2).to_dict()
        
        # Generate insights and recommendations
        insights = generate_insights(df, total_spent, total_received, category_spending)
        recommendations = generate_recommendations(df, category_spending)
        
        result = {
            'total_spent': abs(total_spent),
            'total_received': total_received,
            'net_balance': float(total_received + total_spent),
            'categories': category_spending,
            'insights': insights,
            'recommendations': recommendations
        }
        
        print("Analysis completed successfully")
        return result
        
    except Exception as e:
        print(f"Error in analyze_transactions: {str(e)}")
        raise

def format_currency(value):
    """Format currency values consistently"""
    return f"R$ {abs(value):,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')

def generate_insights(df, total_spent, total_received, category_spending):
    """Generate insights from Nubank transactions"""
    insights = []
    
    # Financial Status Alert
    net_balance = total_received + total_spent
    if net_balance < 0:
        insights.append("🚨 ALERTA: Seus gastos excederam sua receita este mês! 🚨")
    
    # Basic financial insights
    insights.append(f"💰 Total gasto: {format_currency(total_spent)}")
    insights.append(f"📈 Total recebido: {format_currency(total_received)}")
    insights.append(f"🏦 Saldo: {format_currency(net_balance)}")
    
    # Category Analysis
    if category_spending:
        sorted_categories = sorted(category_spending.items(), key=lambda x: x[1], reverse=True)
        insights.append("\n📊 Principais categorias de gastos:")
        for category, amount in sorted_categories[:3]:
            percentage = (amount / abs(total_spent)) * 100
            insights.append(f"- {category}: {format_currency(amount)} ({percentage:.1f}%)")
        
        # Category alerts
        total_spending = sum(category_spending.values())
        for category, amount in category_spending.items():
            percentage = (amount / total_spending) * 100
            if percentage > 30:
                insights.append(f"⚠️ Alerta de gasto alto: {category} representa {percentage:.1f}% de suas despesas")
    
    # Frequent places (only negative amounts and excluding transfers)
    frequent_df = df[
        (df['amount'] < 0) & 
        (~df['description'].str.lower().str.contains('pix|transferencia|pagamento|ted|doc', na=False))
    ]
    
    if not frequent_df.empty:
        frequent_places = frequent_df['description'].apply(simplify_description).value_counts()
        if not frequent_places.empty:
            insights.append("\n🏪 Lugares mais frequentes:")
            for place, count in frequent_places.head(5).items():
                insights.append(f"- {place}: {count} {'vez' if count == 1 else 'vezes'}")
    
    # Large expenses (excluding transfers)
    large_expenses = df[
        (df['amount'] < -100) & 
        (~df['description'].str.lower().str.contains('pix|transferencia|pagamento|ted|doc', na=False))
    ].sort_values('amount')
    
    if not large_expenses.empty:
        insights.append("\n💸 Maiores despesas:")
        for _, row in large_expenses.head(3).iterrows():
            insights.append(f"- {format_currency(abs(row['amount']))} em {simplify_description(row['description'])}")
    
    # Daily patterns
    df['day_of_week'] = df['date'].dt.day_name().map({
        'Monday': 'Segunda-feira',
        'Tuesday': 'Terça-feira',
        'Wednesday': 'Quarta-feira',
        'Thursday': 'Quinta-feira',
        'Friday': 'Sexta-feira',
        'Saturday': 'Sábado',
        'Sunday': 'Domingo'
    })
    
    daily_spending = df[df['amount'] < 0].groupby('day_of_week')['amount'].sum().abs()
    if not daily_spending.empty:
        max_spending_day = daily_spending.idxmax()
        min_spending_day = daily_spending.idxmin()
        insights.append(f"\n📅 Padrões de gasto:")
        insights.append(f"- Dia com mais gastos: {max_spending_day}")
        insights.append(f"- Dia com menos gastos: {min_spending_day}")
    
    return insights

def translate_category(category):
    """Translate category names to Portuguese"""
    # This function is no longer needed since we're using Portuguese categories directly
    return category

def generate_recommendations(df, category_spending):
    """Generate recommendations based on spending patterns"""
    recommendations = []
    
    # Financial Health Score (0-100)
    total_spent = abs(df[df['amount'] < 0]['amount'].sum())
    total_received = df[df['amount'] > 0]['amount'].sum()
    net_balance = total_received + total_spent
    
    if net_balance < 0:
        recommendations.append({
            'priority': 'high',
            'category': 'orçamento',
            'title': '🚨 Urgente: Saldo Negativo',
            'description': 'Seus gastos excederam sua receita. Considere ajustes imediatos no orçamento.',
            'actions': [
                'Revise todas as assinaturas e cancele as não essenciais',
                'Implemente um congelamento de gastos não essenciais',
                'Procure fontes adicionais de renda'
            ]
        })
    
    # Category-specific recommendations
    for category, amount in category_spending.items():
        if category == 'restaurantes' and amount > 500:
            recommendations.append({
                'priority': 'medium',
                'category': 'alimentação',
                'title': '🍽️ Alto Gasto com Restaurantes',
                'description': f'Você gastou R$ {amount:.2f} em restaurantes este mês.',
                'actions': [
                    'Prepare mais refeições em casa',
                    'Use planejamento de refeições para reduzir desperdício',
                    'Procure promoções e pratos do dia'
                ]
            })
    
    # Spending pattern recommendations
    daily_spending = df[df['amount'] < 0].groupby(df['date'].dt.date)['amount'].sum().abs()
    if daily_spending.std() > daily_spending.mean() * 0.5:
        recommendations.append({
            'priority': 'medium',
            'category': 'hábitos',
            'title': '📊 Padrão Irregular de Gastos',
            'description': 'Seus gastos diários variam significativamente.',
            'actions': [
                'Crie um orçamento diário',
                'Acompanhe despesas em tempo real',
                'Planeje compras maiores com antecedência'
            ]
        })
    
    # Add general financial advice
    recommendations.append({
        'priority': 'low',
        'category': 'poupança',
        'title': '💰 Construindo Segurança Financeira',
        'description': 'Recomendações para saúde financeira a longo prazo',
        'actions': [
            'Configure poupança automática de 20% da renda',
            'Crie um fundo de emergência',
            'Revise e ajuste seu orçamento mensalmente'
        ]
    })
    
    return recommendations

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True) 