"""Explorer's look: palette, Plotly template, page styling.

The six hues were validated with the dataviz skill's checker, not eyeballed,
and the same six pass on both surfaces::

    light  #00a3a3,#d1495b,#3d6fd9,#c77d00,#7a4fd0,#3d9a3d  -> all checks pass
    dark   #00a3a3,#d1495b,#3d6fd9,#c77d00,#7a4fd0,#3d9a3d  -> all checks pass

(worst adjacent pair under colour-vision deficiency: ΔE 10.4, target 8.)

Six is the cap the checker passes, and the dictionary has ten event families,
so colour is assigned to six *groups* of families and never cycled. Inside a
group the families differ by marker shape where the chart can draw shapes
(profile, timeline); a map cannot, so there each family is its own legend
entry and names itself on hover.
"""

from typing import Dict

from opdi_explorer import catalogue

#: Colour group -> hue, in fixed order. Colour follows the group, never the
#: number of groups on screen.
GROUP_COLOUR: Dict[str, str] = {
    "Runway": "#00a3a3",
    "Holding and point merge": "#d1495b",
    "Vertical profile": "#3d6fd9",
    "Ground": "#c77d00",
    "Rings and airspace": "#7a4fd0",
    "Track limits": "#3d9a3d",
}

#: An event type the dictionary does not describe: a neutral, so it never
#: borrows the identity of a real group.
NEUTRAL = "#7a7f87"

#: The accent used for single-series charts and for the flight's track.
ACCENT = "#00a3a3"
TRACK = "#4b5563"

#: Family -> marker shape. Two families of one group never share a shape.
FAMILY_SYMBOL: Dict[str, str] = {
    "Take-off and landing": "circle",
    "Other runway events": "diamond",
    "Block times": "square",
    "Airport surface": "circle",
    "Vertical profile": "circle",
    "Distance rings": "circle",
    "Airspace": "diamond",
    "Holding": "circle",
    "Point merge": "diamond",
    "Track limits": "circle",
}

#: Sequential ramp for magnitude (one hue, light to dark).
SEQUENTIAL = [[0.0, "#e6f5f5"], [0.5, "#5cc4c4"], [1.0, "#00696b"]]

MAP_STYLE = "carto-positron"


def colour_of_family(family: str) -> str:
    return GROUP_COLOUR.get(catalogue.group_of(family), NEUTRAL)


def colour_of(type_: str) -> str:
    """The colour an event type wears on every explorer chart."""
    return colour_of_family(catalogue.family_of(type_))


def symbol_of(type_: str) -> str:
    return FAMILY_SYMBOL.get(catalogue.family_of(type_), "x")


def apply(fig, height: int = 380, legend: bool = True):
    """The explorer template: quiet axes, no chart-junk, room for labels."""
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=28, b=8),
        font=dict(family="Inter, system-ui, sans-serif", size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    title_text=""),
        hoverlabel=dict(font_size=13),
        bargap=0.25,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, ticks="outside",
                     ticklen=3, tickcolor="rgba(128,128,128,0.4)")
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.18)", zeroline=False)
    return fig


def page_css() -> str:
    """Styling that makes explorer read as a guide, not a dashboard."""
    return f"""
<style>
  /* The step menu sits in a fixed bar across the top of the page. The first
     thing on the page has to start below it: with less room than this the
     step label slides under the menu. */
  .block-container {{ max-width: 1180px; padding-top: 5.2rem;
                      padding-bottom: 4rem; }}
  .ex-step {{ font-size: 0.8rem; letter-spacing: 0.12em;
              text-transform: uppercase; color: {ACCENT}; font-weight: 700;
              margin-bottom: 0.1rem; }}
  .ex-lead {{ font-size: 1.12rem; line-height: 1.6; max-width: 60rem;
              margin: 0.2rem 0 1.4rem 0; }}
  .ex-card {{ border: 1px solid rgba(128,128,128,0.25); border-radius: 12px;
              padding: 1.1rem 1.3rem; min-height: 9.2rem;
              margin-bottom: 0.9rem; border-top: 4px solid {ACCENT}; }}
  .ex-card h4 {{ margin: 0 0 0.35rem 0; padding: 0; }}
  .ex-card p {{ margin: 0; line-height: 1.55; }}
  .ex-nums {{ display: flex; flex-wrap: wrap; gap: 0.8rem;
              margin: 0.4rem 0 1.1rem 0; }}
  .ex-numbox {{ flex: 1 1 9rem; border-radius: 12px; padding: 0.8rem 1rem;
                background: rgba(0,163,163,0.08); }}
  .ex-num {{ font-size: 1.9rem; font-weight: 700; line-height: 1.15; }}
  .ex-numlabel {{ font-size: 0.85rem; opacity: 0.75; }}
  .ex-q {{ font-size: 1.3rem; font-weight: 650; margin: 2.6rem 0 0.3rem 0;
           padding-top: 1.4rem;
           border-top: 1px solid rgba(128,128,128,0.22); }}
  .ex-tag {{ display: inline-block; padding: 0.08rem 0.6rem;
             border-radius: 999px; font-size: 0.8rem; color: white;
             margin-right: 0.45rem; }}
  .ex-flight {{ border-radius: 14px; padding: 1.1rem 1.4rem;
                margin: 1.2rem 0 0.6rem 0;
                background: rgba(0,163,163,0.08);
                border-left: 5px solid {ACCENT}; }}
  .ex-flight .route {{ font-size: 1.9rem; font-weight: 700;
                       line-height: 1.2; }}
  .ex-flight .sub {{ opacity: 0.8; margin-top: 0.25rem; }}
  .ex-table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem;
               margin: 0.3rem 0 0.8rem 0; }}
  .ex-table th {{ text-align: left; font-weight: 600; opacity: 0.7;
                  padding: 0.45rem 0.7rem; white-space: nowrap;
                  border-bottom: 1px solid rgba(128,128,128,0.35); }}
  .ex-table td {{ padding: 0.45rem 0.7rem; vertical-align: top;
                  border-bottom: 1px solid rgba(128,128,128,0.16);
                  line-height: 1.45; }}
  .ex-table td.k {{ white-space: nowrap; font-family: ui-monospace, monospace;
                    font-size: 0.86rem; }}
  .ex-table td.v {{ font-family: ui-monospace, monospace; font-size: 0.86rem;
                    overflow-wrap: anywhere; min-width: 11rem;
                    max-width: 22rem; }}
  h2 {{ margin-top: 1.6rem; }}
  h3 {{ margin-top: 1.2rem; }}
</style>
"""
