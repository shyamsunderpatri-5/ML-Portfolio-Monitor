"""
📊 GOOGLE SHEETS MANAGER - FIXED VERSION
=========================================
Read and write portfolio data to Google Sheets

Features:
- Read active positions
- Update SL/Target levels
- Log AI decisions
- Track changes history

FIXES APPLIED:
- gspread imported at module level
- Status filter handles NaN
- batch_update uses correct parameters
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging
import os

logger = logging.getLogger(__name__)

# ============================================================================
# IMPORT GSPREAD AT MODULE LEVEL (CRITICAL FIX!)
# ============================================================================
try:
    import gspread
    from gspread.utils import rowcol_to_a1  # Import utility function directly
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    gspread = None
    rowcol_to_a1 = None
    logger.warning("⚠️ gspread not installed. Run: pip install gspread google-auth")


# ============================================================================
# CONFIGURATION
# ============================================================================

SHEETS_CONFIG = {
    'sheet_id': '155htPsyom2e-dR5BZJx_cFzGxjQQjePJt3H2sRLSr6w',  # Your sheet ID
    'main_sheet': 'Portfolio',  # Main positions sheet
    'log_sheet': 'AI_Log',   # AI decisions log (create this sheet)
}


class GoogleSheetsManager:
    """
    Manages Google Sheets read/write operations
    """
    
    def __init__(self, sheet_id: str = None):
        self.sheet_id = sheet_id or SHEETS_CONFIG['sheet_id']
        self.use_api = False
        self.client = None
        
        self._init_client()
    
    def _init_client(self):
        """Initialize Google Sheets client"""
        if not GSPREAD_AVAILABLE:
            logger.warning("⚠️ gspread not available. Using read-only CSV mode.")
            self.use_api = False
            return
        
        try:
            # Check for credentials file
            creds_file = os.getenv('GOOGLE_CREDS_FILE', 'google_credentials.json')
            
            if os.path.exists(creds_file):
                scopes = [
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
                creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
                self.client = gspread.authorize(creds)
                self.use_api = True
                logger.info("✅ Google Sheets API connected")
            else:
                logger.warning(f"⚠️ Credentials file '{creds_file}' not found. Using read-only CSV mode.")
                self.use_api = False
        
        except Exception as e:
            logger.error(f"Google Sheets init error: {e}")
            self.use_api = False
    
    def read_portfolio(self) -> Optional[pd.DataFrame]:
        """
        Read portfolio from Google Sheets
        """
        try:
            if self.use_api and self.client:
                # Use API
                sheet = self.client.open_by_key(self.sheet_id)
                worksheet = sheet.worksheet(SHEETS_CONFIG['main_sheet'])
                data = worksheet.get_all_records()
                df = pd.DataFrame(data)
            else:
                # Use CSV export (read-only)
                export_url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv&gid=0"
                df = pd.read_csv(export_url)
            
            # Filter active positions - FIXED to handle NaN
            if 'Status' in df.columns:
                df = df[df['Status'].astype(str).str.upper().str.strip() == 'ACTIVE']
            
            # Clean column names
            df.columns = df.columns.str.strip()
            
            logger.info(f"✅ Loaded {len(df)} active positions from Google Sheets")
            return df
        
        except Exception as e:
            logger.error(f"Failed to read portfolio: {e}")
            return None
    
    def update_position_levels(
        self,
        ticker: str,
        new_sl: Optional[float] = None,
        new_target1: Optional[float] = None,
        new_target2: Optional[float] = None,
        reason: str = "AI Update"
    ) -> bool:
        """
        Update SL/Target levels for a position
        
        Args:
            ticker: Stock ticker
            new_sl: New stop loss value
            new_target1: New target 1 value
            new_target2: New target 2 value
            reason: Reason for update
        
        Returns:
            True if successful, False otherwise
        """
        if not self.use_api or not self.client:
            logger.warning("Cannot update: API not available (read-only mode)")
            logger.info("💡 To enable updates, create 'google_credentials.json' with service account credentials")
            return False
        
        if not GSPREAD_AVAILABLE:
            logger.warning("Cannot update: gspread not installed")
            return False
        
        try:
            sheet = self.client.open_by_key(self.sheet_id)
            worksheet = sheet.worksheet(SHEETS_CONFIG['main_sheet'])
            
            # Find the row with this ticker
            cell = None
            try:
                cell = worksheet.find(ticker)
            except:
                pass
            
            if not cell:
                # Try with .NS suffix
                try:
                    cell = worksheet.find(f"{ticker}.NS")
                except:
                    pass
            
            if not cell:
                # Try without .NS suffix
                clean_ticker = ticker.replace('.NS', '').replace('.BO', '')
                try:
                    cell = worksheet.find(clean_ticker)
                except:
                    pass
            
            if not cell:
                logger.warning(f"Ticker {ticker} not found in sheet")
                return False
            
            row = cell.row
            
            # Get header row to find column indices
            headers = worksheet.row_values(1)
            
            updates = []
            
            # Prepare updates
            if new_sl is not None:
                col_name = 'Stop_Loss'
                if col_name in headers:
                    col = headers.index(col_name) + 1
                    cell_addr = rowcol_to_a1(row, col)
                    updates.append({
                        'range': cell_addr,
                        'values': [[round(new_sl, 2)]]
                    })
                    logger.info(f"  SL update: {cell_addr} = {new_sl}")
            
            if new_target1 is not None:
                col_name = 'Target_1'
                if col_name in headers:
                    col = headers.index(col_name) + 1
                    cell_addr = rowcol_to_a1(row, col)
                    updates.append({
                        'range': cell_addr,
                        'values': [[round(new_target1, 2)]]
                    })
                    logger.info(f"  T1 update: {cell_addr} = {new_target1}")
            
            if new_target2 is not None:
                col_name = 'Target_2'
                if col_name in headers:
                    col = headers.index(col_name) + 1
                    cell_addr = rowcol_to_a1(row, col)
                    updates.append({
                        'range': cell_addr,
                        'values': [[round(new_target2, 2)]]
                    })
                    logger.info(f"  T2 update: {cell_addr} = {new_target2}")
            
            # Execute batch update
            if updates:
                worksheet.batch_update(updates, value_input_option='RAW')
                logger.info(f"✅ Updated {ticker}: SL={new_sl}, T1={new_target1}, T2={new_target2}")
                
                # Log the change
                self._log_change(ticker, new_sl, new_target1, new_target2, reason)
                
                return True
            else:
                logger.warning(f"No valid updates for {ticker} - columns may not exist")
                return False
        
        except Exception as e:
            logger.error(f"Failed to update {ticker}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _log_change(
        self,
        ticker: str,
        new_sl: Optional[float],
        new_target1: Optional[float],
        new_target2: Optional[float],
        reason: str
    ):
        """Log the change to AI_Log sheet"""
        if not self.use_api or not self.client:
            return
        
        try:
            sheet = self.client.open_by_key(self.sheet_id)
            
            # Try to get or create AI_Log sheet
            try:
                log_sheet = sheet.worksheet(SHEETS_CONFIG['log_sheet'])
            except gspread.exceptions.WorksheetNotFound:
                # Create the sheet if it doesn't exist
                log_sheet = sheet.add_worksheet(title=SHEETS_CONFIG['log_sheet'], rows=1000, cols=10)
                log_sheet.append_row(['Timestamp', 'Ticker', 'New_SL', 'New_Target1', 'New_Target2', 'Reason'])
                logger.info(f"✅ Created '{SHEETS_CONFIG['log_sheet']}' sheet for logging")
            
            # Append log entry
            log_sheet.append_row([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ticker,
                round(new_sl, 2) if new_sl else '',
                round(new_target1, 2) if new_target1 else '',
                round(new_target2, 2) if new_target2 else '',
                reason
            ])
            logger.info(f"📝 Logged change for {ticker}")
        
        except Exception as e:
            logger.warning(f"Failed to log change: {e}")
    
    def batch_update_positions(self, updates: List[Dict]) -> int:
        """
        Batch update multiple positions
        
        Args:
            updates: List of dicts with {ticker, new_sl, new_target1, new_target2, reason}
        
        Returns:
            Number of successful updates
        """
        success_count = 0
        
        for update in updates:
            try:
                if self.update_position_levels(
                    ticker=update.get('ticker'),
                    new_sl=update.get('new_sl'),
                    new_target1=update.get('new_target1'),
                    new_target2=update.get('new_target2'),
                    reason=update.get('reason', 'AI Batch Update')
                ):
                    success_count += 1
            except Exception as e:
                logger.error(f"Batch update failed for {update.get('ticker')}: {e}")
        
        logger.info(f"📊 Batch update: {success_count}/{len(updates)} successful")
        return success_count
    
    def get_status(self) -> Dict:
        """Get current connection status"""
        return {
            'gspread_installed': GSPREAD_AVAILABLE,
            'api_connected': self.use_api,
            'sheet_id': self.sheet_id,
            'can_read': True,  # CSV always works
            'can_write': self.use_api
        }


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================
sheets_manager = GoogleSheetsManager()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def update_portfolio_from_ai(recommendations: List[Dict]) -> Dict:
    """
    Update Google Sheet based on AI recommendations
    
    Args:
        recommendations: List of AI recommendations from trading_brain
    
    Returns:
        Dict with update statistics
    """
    updates_needed = []
    
    for rec in recommendations:
        if rec.get('any_change') and rec.get('should_alert'):
            updates_needed.append({
                'ticker': rec.get('ticker'),
                'new_sl': rec.get('new_sl'),
                'new_target1': rec.get('new_target1'),
                'new_target2': rec.get('new_target2'),
                'reason': rec.get('summary', 'AI Update')
            })
    
    result = {
        'total_recommendations': len(recommendations),
        'updates_needed': len(updates_needed),
        'updates_successful': 0,
        'updates_failed': 0,
        'can_write': sheets_manager.use_api
    }
    
    if updates_needed:
        if sheets_manager.use_api:
            success = sheets_manager.batch_update_positions(updates_needed)
            result['updates_successful'] = success
            result['updates_failed'] = len(updates_needed) - success
        else:
            logger.warning("Cannot apply updates: API not available (read-only mode)")
            result['updates_failed'] = len(updates_needed)
    
    return result


def test_connection():
    """Test the Google Sheets connection"""
    print("=" * 50)
    print("🧪 TESTING GOOGLE SHEETS CONNECTION")
    print("=" * 50)
    
    status = sheets_manager.get_status()
    print(f"\n📋 Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print(f"\n📖 Testing read...")
    df = sheets_manager.read_portfolio()
    if df is not None:
        print(f"  ✅ Read {len(df)} positions successfully")
        print(f"  Columns: {list(df.columns)}")
    else:
        print(f"  ❌ Read failed")
    
    if sheets_manager.use_api:
        print(f"\n📝 Write access: AVAILABLE")
    else:
        print(f"\n📝 Write access: NOT AVAILABLE (read-only mode)")
        print("  💡 To enable write access:")
        print("    1. Create a Google Cloud project")
        print("    2. Enable Google Sheets API")
        print("    3. Create service account credentials")
        print("    4. Download JSON as 'google_credentials.json'")
        print("    5. Share your sheet with the service account email")
    
    print("\n" + "=" * 50)
    print("✅ Test completed!")
    
    return status


if __name__ == "__main__":
    test_connection()
