"""
Visual Renderer Module

This module handles rendering the CNN-style visual stack including:
- Lower thirds with anchor info
- Ticker
- LIVE tag with timestamp
- Story image with pan/zoom effects
"""

import logging
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime
import math


class LowerThird:
    """Renders lower third graphics with anchor information."""
    
    def __init__(self, config: Dict):
        """
        Initialize lower third renderer.
        
        Args:
            config: Configuration dictionary for lower third
        """
        self.enabled = config.get('enabled', True)
        self.update_per_anchor = config.get('update_per_anchor', True)
        self.height = config.get('height', 120)
        self.font_size = config.get('font_size', 18)
        self.logger = logging.getLogger(__name__)
    
    def render(self, anchor_info: Dict, story_title: str) -> Dict:
        """
        Render lower third for current anchor.
        
        Args:
            anchor_info: Dictionary with anchor name, focus, color
            story_title: Current story title
            
        Returns:
            Render data dictionary
        """
        if not self.enabled:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'height': self.height,
            'font_size': self.font_size,
            'anchor_name': anchor_info.get('anchor_name', ''),
            'focus': anchor_info.get('focus', ''),
            'story': story_title,
            'color': anchor_info.get('color', '#FFFFFF'),
            'text': f"{anchor_info.get('anchor_name', '')} - {anchor_info.get('focus', '')}"
        }


class Ticker:
    """Renders scrolling news ticker."""
    
    def __init__(self, config: Dict):
        """
        Initialize ticker renderer.
        
        Args:
            config: Configuration dictionary for ticker
        """
        self.enabled = config.get('enabled', True)
        self.speed = config.get('speed', 2)
        self.height = config.get('height', 40)
        self.font_size = config.get('font_size', 14)
        self.position = 0
        self.logger = logging.getLogger(__name__)
    
    def update(self, delta_time: float):
        """
        Update ticker position.
        
        Args:
            delta_time: Time elapsed since last update in seconds
        """
        if self.enabled:
            self.position += self.speed * delta_time * 60  # 60 fps assumed
    
    def render(self, ticker_text: str) -> Dict:
        """
        Render ticker.
        
        Args:
            ticker_text: Text to display in ticker
            
        Returns:
            Render data dictionary
        """
        if not self.enabled:
            return {'enabled': False}
        
        return {
            'enabled': True,
            'height': self.height,
            'font_size': self.font_size,
            'position': self.position,
            'text': ticker_text,
            'speed': self.speed
        }


class LiveTag:
    """Renders LIVE tag with timestamp and episode ID."""
    
    def __init__(self, config: Dict, episode_id: str):
        """
        Initialize LIVE tag renderer.
        
        Args:
            config: Configuration dictionary for LIVE tag
            episode_id: Unique episode identifier
        """
        self.enabled = config.get('enabled', True)
        self.position = config.get('position', 'top-left')
        self.show_timestamp = config.get('show_timestamp', True)
        self.show_episode_id = config.get('show_episode_id', True)
        self.episode_id = episode_id
        self.logger = logging.getLogger(__name__)
    
    def render(self) -> Dict:
        """
        Render LIVE tag.
        
        Returns:
            Render data dictionary
        """
        if not self.enabled:
            return {'enabled': False}
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        return {
            'enabled': True,
            'position': self.position,
            'text': 'LIVE',
            'timestamp': timestamp if self.show_timestamp else None,
            'episode_id': self.episode_id if self.show_episode_id else None,
            'display_text': self._format_display_text(timestamp)
        }
    
    def _format_display_text(self, timestamp: str) -> str:
        """Format the complete LIVE tag display text."""
        parts = ['LIVE']
        if self.show_timestamp:
            parts.append(timestamp)
        if self.show_episode_id:
            parts.append(f"EP:{self.episode_id}")
        return ' | '.join(parts)


class StoryImageRenderer:
    """Renders story image with slow pan/zoom effects."""
    
    def __init__(self, config: Dict):
        """
        Initialize story image renderer.
        
        Args:
            config: Configuration dictionary for story image
        """
        self.pan_zoom_enabled = config.get('pan_zoom_enabled', True)
        self.pan_speed = config.get('pan_speed', 0.5)
        self.zoom_factor = config.get('zoom_factor', 1.1)
        self.duration = config.get('duration', 120)
        self.logger = logging.getLogger(__name__)
        
        # Animation state
        self.elapsed_time = 0
        self.current_pan_x = 0
        self.current_pan_y = 0
        self.current_zoom = 1.0
    
    def start_image(self, image_url: Optional[str]):
        """
        Start rendering a new image.
        
        Args:
            image_url: URL of the image to display
        """
        self.image_url = image_url
        self.elapsed_time = 0
        self.current_pan_x = 0
        self.current_pan_y = 0
        self.current_zoom = 1.0
        self.logger.info(f"Started new image: {image_url}")
    
    def update(self, delta_time: float):
        """
        Update pan/zoom animation.
        
        Args:
            delta_time: Time elapsed since last update in seconds
        """
        if not self.pan_zoom_enabled:
            return
        
        self.elapsed_time += delta_time
        
        # Calculate progress through animation cycle (0 to 1)
        progress = (self.elapsed_time % self.duration) / self.duration
        
        # Smooth pan using sine wave
        self.current_pan_x = math.sin(progress * 2 * math.pi) * self.pan_speed * 100
        self.current_pan_y = math.cos(progress * 2 * math.pi) * self.pan_speed * 50
        
        # Smooth zoom using sine wave
        zoom_progress = math.sin(progress * math.pi) * (self.zoom_factor - 1.0)
        self.current_zoom = 1.0 + zoom_progress
    
    def render(self) -> Dict:
        """
        Render story image with current pan/zoom.
        
        Returns:
            Render data dictionary
        """
        return {
            'enabled': True,
            'image_url': getattr(self, 'image_url', None),
            'pan_x': self.current_pan_x,
            'pan_y': self.current_pan_y,
            'zoom': self.current_zoom,
            'elapsed_time': self.elapsed_time
        }


class VisualStack:
    """Manages all visual elements for the broadcast."""
    
    def __init__(self, config: Dict, episode_id: str):
        """
        Initialize visual stack.
        
        Args:
            config: Visual configuration dictionary
            episode_id: Unique episode identifier
        """
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.lower_third = LowerThird(config.get('lower_third', {}))
        self.ticker = Ticker(config.get('ticker', {}))
        self.live_tag = LiveTag(config.get('live_tag', {}), episode_id)
        self.story_image = StoryImageRenderer(config.get('story_image', {}))
        
        # Ticker content
        self.ticker_text = "Breaking news coverage continues 24/7 • Stay tuned for updates"
    
    def update(self, delta_time: float):
        """
        Update all visual components.
        
        Args:
            delta_time: Time elapsed since last update in seconds
        """
        self.ticker.update(delta_time)
        self.story_image.update(delta_time)
    
    def render_frame(self, anchor_info: Dict, story_title: str) -> Dict:
        """
        Render a complete frame with all visual elements.
        
        Args:
            anchor_info: Current anchor information
            story_title: Current story title
            
        Returns:
            Complete frame render data
        """
        return {
            'lower_third': self.lower_third.render(anchor_info, story_title),
            'ticker': self.ticker.render(self.ticker_text),
            'live_tag': self.live_tag.render(),
            'story_image': self.story_image.render(),
            'timestamp': datetime.now().isoformat()
        }
    
    def set_story_image(self, image_url: Optional[str]):
        """Set the current story image."""
        self.story_image.start_image(image_url)
    
    def set_ticker_text(self, text: str):
        """Update ticker text."""
        clean = (text or "").strip()
        if not clean:
            clean = "Breaking news coverage continues 24/7 • Stay tuned for updates"

        bullet_count = clean.count("•")
        if len(clean) < 300 or bullet_count < 3:
            try:
                standby = Path("/home/remvelchio/agent/tmp/ticker_standby.txt").read_text().strip()
                if standby:
                    if clean:
                        clean = f"{clean}  •  {standby}"
                    else:
                        clean = standby
            except FileNotFoundError:
                pass

        self.ticker_text = clean
        Path("/home/remvelchio/agent/tmp/ticker.txt").write_text(clean)
