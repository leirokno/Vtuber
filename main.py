"""
Main entry point for the Agente 24/7 Morning Show Broadcast.

This script starts the broadcast pipeline and runs the main loop.
"""

import yaml
import time
import signal
import sys
from broadcast_pipeline import BroadcastPipeline


def load_config(config_path: str = 'config.yaml') -> dict:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully."""
    print("\n\nReceived shutdown signal, stopping broadcast...")
    if hasattr(signal_handler, 'pipeline'):
        signal_handler.pipeline.stop()
    sys.exit(0)


def main():
    """Main entry point."""
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Load configuration
    print("Loading configuration...")
    config = load_config('config.yaml')
    
    # Create and start pipeline
    pipeline = BroadcastPipeline(config)
    signal_handler.pipeline = pipeline  # Store for signal handler
    
    pipeline.start()
    
    # Main loop
    print("\n24/7 Broadcast is now live!")
    print("Press Ctrl+C to stop\n")
    
    target_fps = 30  # Target frame rate
    frame_time = 1.0 / target_fps
    last_frame_time = time.time()
    last_status_time = time.time()
    
    try:
        while pipeline.running:
            current_time = time.time()
            delta_time = current_time - last_frame_time
            
            # Update pipeline
            pipeline.update(delta_time)
            
            # Render frame
            frame = pipeline.render_frame()
            
            # Print status every 10 seconds
            if current_time - last_status_time >= 10:
                status = pipeline.get_status()
                print(f"\n[STATUS] Episode: {status['episode_id']}")
                print(f"  State: {status['state']}")
                print(f"  Story: {status['current_story']}")
                print(f"  Anchor: {status['current_anchor']}")
                print(f"  Frames: {status['frame_count']}")
                print(f"  Uptime: {status['uptime']:.1f}s")
                if status['anchor_stats']:
                    print(f"  Rotations: {status['anchor_stats']['rotation_count']}")
                last_status_time = current_time
            
            # Frame rate limiting
            elapsed = time.time() - last_frame_time
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
            
            last_frame_time = time.time()
    
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        pipeline.stop()
    except Exception as e:
        print(f"\n\nError in main loop: {e}")
        pipeline.stop()
        raise


if __name__ == '__main__':
    main()
