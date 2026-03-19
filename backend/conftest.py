"""
Pytest configuration and fixtures for PR Tracker backend tests.
Configures hypothesis for property-based testing with minimum 100 iterations.
"""

from hypothesis import settings, Verbosity

# Configure hypothesis settings for all property tests
# Minimum 100 iterations as per design requirements
settings.register_profile("default", max_examples=100, verbosity=Verbosity.normal)
settings.register_profile("ci", max_examples=200, verbosity=Verbosity.verbose)
settings.register_profile("dev", max_examples=100, verbosity=Verbosity.normal)
settings.register_profile("debug", max_examples=10, verbosity=Verbosity.verbose)

# Load the default profile
settings.load_profile("default")
