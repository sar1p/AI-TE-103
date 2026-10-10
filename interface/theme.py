"""Small theme adjustments that use stable, semantic Streamlit containers."""

import streamlit as st


def apply_page_styles() -> None:
    """Set restrained spacing and targeted breakpoints on keyed UI regions."""
    st.html(
        """<style>
        [data-testid="stMainBlockContainer"] {
          max-width: 1480px;
          padding-top: .8rem;
          padding-bottom: 2.5rem;
        }
        [data-testid="stMainBlockContainer"] h1 {
          font-size: 28px !important;
          line-height: 1.15 !important;
          margin-bottom: .25rem !important;
        }
        [data-testid="stMainBlockContainer"] h3 {
          font-size: 20px !important;
          line-height: 1.2 !important;
        }
        .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] {
          align-items: end;
        }
        @media (max-width: 1050px) {
          .st-key-mission_layout [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important;
          }
          .st-key-mission_layout [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
          }
        }
        @media (max-width: 850px) {
          .st-key-diagnostic_preset_toolbar [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
          }
          .st-key-diagnostic_preset_toolbar [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 0 !important;
          }
          .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: wrap !important;
            column-gap: 1rem;
            row-gap: .25rem;
          }
          .st-key-scenario_toolbar [data-testid="stColumn"] {
            min-width: 0 !important;
          }
          .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:first-child {
            flex: 1 1 100% !important;
            width: 100% !important;
          }
          .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(2),
          .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(3) {
            flex: 1 1 calc(50% - .5rem) !important;
            width: calc(50% - .5rem) !important;
          }
        }
        @media (max-width: 600px) {
          .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
          }
          .st-key-scenario_toolbar [data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:nth-child(n) {
            flex: 1 1 100% !important;
            width: 100% !important;
          }
          .st-key-guided_observation_fields [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important;
          }
          .st-key-guided_observation_fields [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
          }
          .st-key-map_header [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: column !important;
          }
          .st-key-map_header [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            width: 100% !important;
            max-width: 100% !important;
            min-width: 0 !important;
          }
        }
        </style>"""
    )
