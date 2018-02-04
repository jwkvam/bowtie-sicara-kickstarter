#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pendulum
from bowtie import App, command

from bowtie.visual import Markdown, Plotly
from bowtie.control import Dropdown

import plotly.graph_objs as go
import plotlywrapper as pw

import pandas as pd

kickstarter_df = pd.read_csv('kickstarter-cleaned.csv', parse_dates=False)
kickstarter_df['broader_category'] = kickstarter_df['category_slug'].str.split('/').str.get(0)
kickstarter_df['created_at'] = pd.to_datetime(kickstarter_df['created_at'])
kickstarter_df_sub = kickstarter_df.sample(10000)

CATEGORIES = kickstarter_df['broader_category'].unique()
COLUMNS = ['launched_at', 'deadline', 'blurb', 'usd_pledged', 'state',
           'spotlight', 'staff_pick', 'category_slug', 'backers_count', 'country']
# Picked with http://tristen.ca/hcl-picker/#/hlc/6/1.05/251C2A/E98F55
COLORS = ['#7DFB6D', '#C7B815', '#D4752E', '#C7583F']
STATES = ['successful', 'suspended', 'failed', 'canceled']

cats = kickstarter_df.broader_category.unique()

header = Markdown('# Kickstarter Dashboard')
select = Dropdown(labels=cats, values=cats, multi=True)
pledged = Plotly()
counts = Plotly()


def init():
    z = select.get()
    if z is None:
        update_pledged()
        update_counts()


def get_categories(categories=None):
    if categories:
        return [x['value'] for x in categories]
    return CATEGORIES


def update_pledged(categories=None):
    categories = get_categories(categories)

    sub_df = kickstarter_df_sub[kickstarter_df_sub.broader_category.isin(categories)]

    pdict = {
        'data': [
            go.Scatter(
                x=sub_df[kickstarter_df_sub.state == state].created_at,
                y=sub_df[kickstarter_df_sub.state == state].usd_pledged,
                text=sub_df[kickstarter_df_sub.state == state].name,
                mode='markers',
                opacity=0.7,
                marker={
                    'size': 15,
                    'color': color,
                    'line': {'width': 0.5, 'color': 'white'}
                },
                name=state,
            ) for (state, color) in zip(STATES, COLORS)
        ],
        'layout': go.Layout(
            xaxis={'title': 'Date'},
            yaxis={'title': 'USD pledged', 'type': 'log'},
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            legend={'x': 0, 'y': 1},
            hovermode='closest'
        )
    }
    pledged.do_all(pdict)


def update_counts(categories=None, layout=None):
    categories = get_categories(categories)

    print(layout)
    if layout is not None and 'xaxis.autorange' not in layout:
        x0 = pendulum.parse(layout['xaxis.range[0]'])
        x1 = pendulum.parse(layout['xaxis.range[1]'])
        y0 = 10 ** layout['yaxis.range[0]']
        y1 = 10 ** layout['yaxis.range[1]']

        sub_df = kickstarter_df[kickstarter_df.created_at.between(x0, x1) & kickstarter_df.usd_pledged.between(y0, y1)]
    else:
        sub_df = kickstarter_df

    sub_df = sub_df[sub_df.broader_category.isin(categories)]

    stacked_barchart_df = (
        sub_df.groupby('broader_category').state
        .value_counts()
    )
    stacked_barchart_df = stacked_barchart_df.reindex(
        pd.MultiIndex.from_product([categories, STATES], names=stacked_barchart_df.index.names),
        fill_value=0
    )
    stacked_barchart_df = (
        stacked_barchart_df.rename('count')
        .to_frame()
        .reset_index('state')
        .pivot(columns='state')
        .reset_index()
    )
    counts.do_all({
        'data': [
            go.Bar(
                x=stacked_barchart_df.broader_category,
                y=stacked_barchart_df['count'][state],
                name=state,
                marker={
                    'color': color
                }
            ) for (state, color) in zip(STATES[::-1], COLORS[::-1])
        ],
        'layout': go.Layout(
            yaxis={'title': 'Number of projects'},
            barmode='stack',
            hovermode='closest'
        )
    })


@command
def main():
    app = App(rows=4, sidebar=False, debug=True)
    # set first to rows to auto size
    app.rows[0].auto()
    app.rows[1].auto()

    app.add(header)
    app.add(select)
    app.add(pledged)
    app.add(counts)

    app.load(init)
    app.subscribe(update_pledged, select.on_change)
    app.subscribe(update_counts, select.on_change, pledged.on_relayout)

    return app
