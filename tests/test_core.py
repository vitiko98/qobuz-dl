import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, call, ANY
from qobuz_dl.core import QobuzDL

class TestQobuzDL(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.qobuz = QobuzDL()
        
    def test_file_parsing_with_comments(self):
        """Test parsing file with comments and valid URLs"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("""
# Comment line
https://play.qobuz.com/album/123
https://play.qobuz.com/track/456

# Another comment
            """)
            temp_file = f.name
            
        try:
            with patch('qobuz_dl.core.QobuzDL.handle_url') as mock_handle:
                self.qobuz.download_from_txt_file(temp_file)
                # Should be called twice (once for each URL)
                self.assertEqual(mock_handle.call_count, 2)
        finally:
            os.unlink(temp_file)
            
    def test_empty_file(self):
        """Test handling of empty file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("""
# Only comments
# No URLs
            """)
            temp_file = f.name
            
        try:
            with patch('qobuz_dl.core.logger') as mock_logger:
                self.qobuz.download_from_txt_file(temp_file)
                mock_logger.info.assert_called_with(
                    mock_logger.info.call_args_list[0][0][0]
                )
        finally:
            os.unlink(temp_file)
            
    def test_file_not_found(self):
        """Test handling of nonexistent file"""
        with patch('qobuz_dl.core.logger') as mock_logger:
            self.qobuz.download_from_txt_file("nonexistent_file.txt")
            mock_logger.error.assert_called()
            
    def test_progress_bar_display(self):
        """Test progress bar functionality"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("""
https://play.qobuz.com/album/123
https://play.qobuz.com/track/456
# Comment line
https://play.qobuz.com/album/789
            """)
            temp_file = f.name
            
        try:
            with patch('qobuz_dl.core.tqdm') as mock_tqdm:
                # Create a mock that properly simulates the iterable behavior
                mock_iter = MagicMock()
                mock_iter.__iter__.return_value = ['line1', 'line2', 'line3']
                mock_tqdm.return_value = mock_iter
                
                with patch('qobuz_dl.core.QobuzDL.handle_url') as mock_handle:
                    self.qobuz.download_from_txt_file(temp_file)
                    
                    # Verify tqdm was called twice
                    assert mock_tqdm.call_count == 2
                    
                    # Get all calls made to tqdm
                    calls = mock_tqdm.mock_calls
                    
                    # Check that both calls have the correct descriptions
                    assert any(call for call in calls if "desc='Parsing URLs'" in str(call))
                    assert any(call for call in calls if "desc='Processing URLs'" in str(call))
                    
                    # Verify handle_url was called for each non-comment URL
                    assert mock_handle.call_count == 3
        finally:
            os.unlink(temp_file)

if __name__ == '__main__':
    unittest.main()