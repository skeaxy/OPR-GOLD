
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import pytz
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Optional
import warnings
warnings.filterwarnings('ignore')

@dataclass
class Trade:
    entry_time: datetime
    entry_price: float
    direction: str  # 'long' ou 'short'
    stop_loss: float
    take_profit: float
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    status: str = 'open'  # 'open', 'win', 'loss'

class GoldFutureStrategy:
    def __init__(self, symbol='GC=F', risk_reward_ratio=2.0):
        """
        """
        self.symbol = symbol
        self.risk_reward_ratio = risk_reward_ratio
        self.london_tz = pytz.timezone('Europe/London')
        self.trades = []
        
    def get_data(self, start_date, end_date, interval='1m'):
        """
        """
        try:
            ticker = yf.Ticker(self.symbol)
            data = ticker.history(start=start_date, end=end_date, interval=interval)
            if data.empty:
                print(f"Aucune donnée trouvée pour {self.symbol}")
                return None
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération des données: {e}")
            return None
    
    def identify_london_session_start(self, date):
        """
        """
        london_open = self.london_tz.localize(
            datetime.combine(date, time(8, 0))
        ).astimezone(pytz.UTC)
        return london_open
    
    def calculate_london_rectangle(self, data, date):
        """
        """
        london_start = self.identify_london_session_start(date)
        london_end = london_start + timedelta(minutes=15)
        
        mask = (data.index >= london_start) & (data.index < london_end)
        london_data = data[mask]
        
        if london_data.empty:
            return None, None, None
        
        high_15min = london_data['High'].max()
        low_15min = london_data['Low'].min()
        
        return high_15min, low_15min, london_data
    
    def check_breakout(self, data, high_level, low_level, start_time):
        """
        """
        mask = data.index > start_time
        post_rectangle_data = data[mask]
        
        if post_rectangle_data.empty:
            return None
        
        for idx, row in post_rectangle_data.iterrows():
            if row['Close'] > high_level:
                return {
                    'time': idx,
                    'direction': 'long',
                    'entry_price': row['Close'],
                    'breakout_candle_high': row['High'],
                    'breakout_candle_low': row['Low']
                }
            
            elif row['Close'] < low_level:
                return {
                    'time': idx,
                    'direction': 'short',
                    'entry_price': row['Close'],
                    'breakout_candle_high': row['High'],
                    'breakout_candle_low': row['Low']
                }
        
        return None
    
    def calculate_stop_loss_take_profit(self, breakout_info):
        """
        """
        direction = breakout_info['direction']
        entry_price = breakout_info['entry_price']
        
        if direction == 'long':
            stop_loss = breakout_info['breakout_candle_low']
            risk = entry_price - stop_loss
            take_profit = entry_price + (risk * self.risk_reward_ratio)
        else:  # short
            stop_loss = breakout_info['breakout_candle_high']
            risk = stop_loss - entry_price
            take_profit = entry_price - (risk * self.risk_reward_ratio)
        
        return stop_loss, take_profit
    
    def simulate_trade_outcome(self, data, trade_info, stop_loss, take_profit):
        """
        """
        start_time = trade_info['time']
        direction = trade_info['direction']
        entry_price = trade_info['entry_price']
        mask = data.index > start_time
        future_data = data[mask]
        
        if future_data.empty:
            return None, None, None
        
        for idx, row in future_data.iterrows():
            if direction == 'long':
                # Vérifier si stop loss touché
                if row['Low'] <= stop_loss:
                    return idx, stop_loss, 'loss'
                # Vérifier si take profit touché
                elif row['High'] >= take_profit:
                    return idx, take_profit, 'win'
            else:  # short
                # Vérifier si stop loss touché
                if row['High'] >= stop_loss:
                    return idx, stop_loss, 'loss'
                # Vérifier si take profit touché
                elif row['Low'] <= take_profit:
                    return idx, take_profit, 'win'
        return None, None, 'open'
    
    def run_strategy(self, start_date, end_date):
        """
        """
        print(f"Récupération des données pour {self.symbol} du {start_date} au {end_date}")
        data = self.get_data(start_date, end_date, '1m')
        
        if data is None:
            return
        if data.index.tz is None:
            data.index = data.index.tz_localize('UTC')
        elif data.index.tz != pytz.UTC:
            data.index = data.index.tz_convert('UTC')
        dates = pd.to_datetime(data.index.date).unique()
        
        print(f"Analyse de {len(dates)} jours de trading...")
        
        for date in dates:
            high_15min, low_15min, london_data = self.calculate_london_rectangle(data, date.date())
            
            if high_15min is None:
                continue
            
            print(f"\nDate: {date.date()}")
            print(f"Rectangle Londres - Haut: {high_15min:.2f}, Bas: {low_15min:.2f}")
        
            rectangle_end = london_data.index[-1] if len(london_data) > 0 else None
            if rectangle_end is None:
                continue
            
            breakout = self.check_breakout(data, high_15min, low_15min, rectangle_end)
            
            if breakout:
                print(f"🚨 BREAKOUT DÉTECTÉ: {breakout['direction'].upper()} à {breakout['time'].strftime('%H:%M:%S')}")
                print(f"📊 Bougie de breakout - Haut: {breakout['breakout_candle_high']:.2f}, Bas: {breakout['breakout_candle_low']:.2f}")
                
                stop_loss, take_profit = self.calculate_stop_loss_take_profit(breakout)
                
                if breakout['direction'] == 'long':
                    risk = breakout['entry_price'] - stop_loss
                    reward = take_profit - breakout['entry_price']
                else:
                    risk = stop_loss - breakout['entry_price']
                    reward = breakout['entry_price'] - take_profit
                
                print(f"💰 POSITION {breakout['direction'].upper()}:")
                print(f"   • Prix d'entrée: {breakout['entry_price']:.2f} (clôture bougie 1min)")
                print(f"   • Stop Loss: {stop_loss:.2f} (basé sur {('bas' if breakout['direction'] == 'long' else 'haut')} bougie breakout)")
                print(f"   • Take Profit: {take_profit:.2f} (ratio 1:{self.risk_reward_ratio})")
                print(f"   • Risque: {risk:.2f} points")
                print(f"   • Récompense: {reward:.2f} points")
                
                exit_time, exit_price, status = self.simulate_trade_outcome(data, breakout, stop_loss, take_profit)
                
                if status == 'win':
                    pnl = take_profit - breakout['entry_price'] if breakout['direction'] == 'long' else breakout['entry_price'] - take_profit
                elif status == 'loss':
                    pnl = stop_loss - breakout['entry_price'] if breakout['direction'] == 'long' else breakout['entry_price'] - stop_loss
                else:
                    pnl = None
                
                trade = Trade(
                    entry_time=breakout['time'],
                    entry_price=breakout['entry_price'],
                    direction=breakout['direction'],
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    exit_time=exit_time,
                    exit_price=exit_price,
                    pnl=pnl,
                    status=status
                )
                
                self.trades.append(trade)
                
                if exit_time:
                    print(f"   • Sortie: {exit_time.strftime('%H:%M:%S')} à {exit_price:.2f}")
                    if status == 'win':
                        print(f"   ✅ GAIN: +{pnl:.2f} points")
                    else:
                        print(f"   ❌ PERTE: {pnl:.2f} points")
                else:
                    print(f"   ⏳ Position ouverte (pas de SL/TP touché dans les données)")
            else:
                print("Aucun breakout détecté")
    
    def generate_statistics(self):
        """

        """
        if not self.trades:
            print("Aucun trade à analyser")
            return
        
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.status == 'win']
        losing_trades = [t for t in self.trades if t.status == 'loss']
        open_trades = [t for t in self.trades if t.status == 'open']
        
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        total_pnl = sum([t.pnl for t in self.trades if t.pnl is not None])
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        print("="*50)
        print("STATISTIQUES DE TRADING")
        print("="*50)
        print(f"Nombre total de trades: {total_trades}")
        print(f"Trades gagnants: {len(winning_trades)}")
        print(f"Trades perdants: {len(losing_trades)}")
        print(f"Trades ouverts: {len(open_trades)}")
        print(f"Taux de réussite: {win_rate:.2f}%")
        print(f"P&L total: {total_pnl:.2f}")
        print(f"Gain moyen: {avg_win:.2f}")
        print(f"Perte moyenne: {avg_loss:.2f}")
        
        if len(winning_trades) > 0 and len(losing_trades) > 0:
            profit_factor = abs(avg_win * len(winning_trades)) / abs(avg_loss * len(losing_trades))
            print(f"Profit Factor: {profit_factor:.2f}")
    
    def print_all_trades(self):
        """
        """
        if not self.trades:
            print("Aucun trade à afficher")
            return
        
        print("\n" + "="*80)
        print("DÉTAIL DE TOUTES LES POSITIONS")
        print("="*80)
        
        for i, trade in enumerate(self.trades, 1):
            print(f"\nTrade #{i}")
            print(f"Date d'entrée: {trade.entry_time}")
            print(f"Direction: {trade.direction.upper()}")
            print(f"Prix d'entrée: {trade.entry_price:.2f}")
            print(f"Stop Loss: {trade.stop_loss:.2f}")
            print(f"Take Profit: {trade.take_profit:.2f}")
            
            if trade.exit_time:
                print(f"Date de sortie: {trade.exit_time}")
                print(f"Prix de sortie: {trade.exit_price:.2f}")
            
            print(f"Statut: {trade.status.upper()}")
            
            if trade.pnl is not None:
                print(f"P&L: {trade.pnl:.2f} ({'Gain' if trade.pnl > 0 else 'Perte'})")
            
            print("-" * 40)
    
    def plot_trades(self, date=None):
        """
        """
        pass

def main():
    strategy = GoldFutureStrategy(symbol='GC=F', risk_reward_ratio=3.0)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print("🎆 Démarrage de l'analyse de la stratégie Gold Future")
    print(f"📅 Période: {start_date.date()} à {end_date.date()} (7 jours)")
    print(f"💰 Symbole: {strategy.symbol}")
    print(f"🎯 Ratio Risk/Reward: 1:{strategy.risk_reward_ratio}")
    print(f"⏱️ Précision: Données 1 minute")
    print(f"🌍 Session: Londres (8h00-8h15 GMT)")
    print("\n" + "="*60)
    
    strategy.run_strategy(start_date, end_date)
    
    strategy.generate_statistics()
    strategy.print_all_trades()

if __name__ == "__main__":
    main()
