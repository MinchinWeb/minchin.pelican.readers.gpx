from blinker import signal

gpx_generator_init = signal("gpx_generator_init")
gpx_generator_preread = signal("gpx_generator_preread")
gpx_generator_context = signal("gpx_generator_context")
gpx_generator_write_gpx = signal("gpx_generator_write_gpx")
gpx_writer_finalized = signal("gpx_writer_finalized")
gpx_generator_finalized = signal("gox__generator_finalized")
