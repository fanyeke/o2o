#!/usr/bin/env python3
"""O2O Coupon Usage + Online Retail Data Analysis Report Generator."""

import warnings
warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from matplotlib.font_manager import FontProperties
import seaborn as sns
from jinja2 import Template
from pathlib import Path
from datetime import datetime
import os

# ============================================================
# Configuration
# ============================================================
sns.set_style('whitegrid')
sns.set_context('talk')

# Resolve paths relative to script location (project root)
SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_DIR = SCRIPT_DIR / 'data'
HTML_DIR = SCRIPT_DIR / 'html'
CHARTS_DIR = HTML_DIR / 'charts'
CHARTS_DIR.mkdir(exist_ok=True)

FONT = FontProperties(family='Noto Sans SC', weight='normal')

def save_chart(fig, name, dpi=150):
    """Save figure to charts dir and return relative path."""
    path = CHARTS_DIR / f'{name}.png'
    fig.savefig(path, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return f'charts/{name}.png'

def set_chinese_font(ax=None):
    """Apply Chinese font to axes."""
    if ax:
        for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] +
                     ax.get_xticklabels() + ax.get_yticklabels()):
            item.set_fontproperties(FONT)
    else:
        for label in (plt.gca().get_xticklabels() + plt.gca().get_yticklabels()):
            label.set_fontproperties(FONT)


# ============================================================
# 1. Data Loading & Preprocessing
# ============================================================
def load_offline_train():
    print('Loading offline_train.csv...')
    df = pd.read_csv(DATA_DIR / 'offline_train.csv', dtype={
        'User_id': str, 'Merchant_id': str, 'Coupon_id': str,
        'Discount_rate': str, 'Distance': str, 'Date_received': str, 'Date': str
    })
    df['Coupon_id'] = df['Coupon_id'].replace('null', np.nan)
    df['Discount_rate'] = df['Discount_rate'].replace('null', np.nan)
    df['Distance'] = df['Distance'].replace('null', np.nan)
    df['Date_received'] = pd.to_datetime(df['Date_received'], format='%Y%m%d', errors='coerce')
    df['Date'] = pd.to_datetime(df['Date'], format='%Y%m%d', errors='coerce')

    df['has_coupon'] = df['Coupon_id'].notna()
    df['is_used'] = df['has_coupon'] & df['Date'].notna()
    df['Distance'] = pd.to_numeric(df['Distance'], errors='coerce')
    df['discount_type'] = df['Discount_rate'].apply(
        lambda x: '满减' if isinstance(x, str) and ':' in x else ('折扣' if isinstance(x, str) else None)
    )

    def parse_discount(x):
        if pd.isna(x):
            return np.nan
        if ':' in x:
            try:
                threshold, discount = x.split(':')
                return round(float(discount) / float(threshold), 4)
            except (ValueError, ZeroDivisionError):
                return np.nan
        else:
            try:
                return round(1 - float(x), 4)
            except (ValueError, TypeError):
                return np.nan
    df['discount_value'] = df['Discount_rate'].apply(parse_discount)
    df['days_to_use'] = (df['Date'] - df['Date_received']).dt.days
    df['weekday_received'] = df['Date_received'].dt.weekday
    df['month_received'] = df['Date_received'].dt.month
    return df

def load_offline_test():
    print('Loading offline_test.csv...')
    df = pd.read_csv(DATA_DIR / 'offline_test.csv', dtype={
        'User_id': str, 'Merchant_id': str, 'Coupon_id': str,
        'Discount_rate': str, 'Distance': str, 'Date_received': str
    })
    df['Coupon_id'] = df['Coupon_id'].replace('null', np.nan)
    df['Discount_rate'] = df['Discount_rate'].replace('null', np.nan)
    df['Distance'] = df['Distance'].replace('null', np.nan)
    df['Date_received'] = pd.to_datetime(df['Date_received'], format='%Y%m%d', errors='coerce')
    df['Distance'] = pd.to_numeric(df['Distance'], errors='coerce')
    df['discount_type'] = df['Discount_rate'].apply(
        lambda x: '满减' if isinstance(x, str) and ':' in x else ('折扣' if isinstance(x, str) else None)
    )
    df['discount_value'] = df['Discount_rate'].apply(lambda x: np.nan if pd.isna(x) else (
        round(float(x.split(':')[1]) / float(x.split(':')[0]), 4) if ':' in str(x) else round(1 - float(x), 4)
    ))
    df['weekday_received'] = df['Date_received'].dt.weekday
    df['month_received'] = df['Date_received'].dt.month
    return df

def load_online_retail():
    print('Loading Online Retail.xlsx...')
    df = pd.read_excel(DATA_DIR / 'Online Retail.xlsx')
    df.columns = df.columns.str.strip()
    df['InvoiceDate'] = pd.to_datetime(df['InvoiceDate'])
    df['Revenue'] = df['Quantity'] * df['UnitPrice']
    df['is_cancellation'] = df['InvoiceNo'].astype(str).str.startswith('C')
    df['is_return'] = df['Quantity'] < 0
    df['month'] = df['InvoiceDate'].dt.month
    df['year'] = df['InvoiceDate'].dt.year
    df['month_year'] = df['InvoiceDate'].dt.to_period('M')
    return df


# ============================================================
# 2. Chart Generation - O2O Coupon Analysis
# ============================================================
def chart_data_overview(train, test):
    """Chart 01: Data overview - shapes, missing values."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('数据概览', fontsize=16, fontweight='bold', fontproperties=FONT)

    # TL: Row counts
    ax = axes[0, 0]
    labels = ['训练集\n(offline_train)', '测试集\n(offline_test)']
    counts = [len(train), len(test)]
    colors = ['#3b82f6', '#f59e0b']
    bars = ax.bar(labels, counts, color=colors, width=0.5)
    for bar, val in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 20000,
                f'{val:,}', ha='center', va='bottom', fontproperties=FONT, fontsize=11)
    ax.set_ylabel('记录数', fontproperties=FONT)
    ax.set_title('数据量对比', fontproperties=FONT, fontsize=13)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # TR: Missing values in train
    ax = axes[0, 1]
    cols = ['User_id', 'Merchant_id', 'Coupon_id', 'Discount_rate', 'Distance', 'Date_received', 'Date']
    missing = [(train[c].isna().sum() / len(train) * 100) for c in cols]
    colors_m = ['#22c55e' if v < 5 else ('#f59e0b' if v < 50 else '#ef4444') for v in missing]
    bars = ax.barh(cols[::-1], [m for m in missing[::-1]], color=colors_m[::-1], height=0.5)
    ax.set_xlabel('缺失比例 (%)', fontproperties=FONT)
    ax.set_title('训练集缺失值比例', fontproperties=FONT, fontsize=13)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # BL: Train composition
    ax = axes[1, 0]
    has_coupon = train['has_coupon'].sum()
    no_coupon = (~train['has_coupon']).sum()
    used = train['is_used'].sum()
    unused = has_coupon - used
    labels = ['仅浏览\n(无券)', '领券已核销', '领券未核销']
    sizes = [no_coupon, used, unused]
    colors_p = ['#94a3b8', '#22c55e', '#f59e0b']
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors_p, autopct='%1.1f%%',
                            textprops={'fontproperties': FONT, 'fontsize': 10},
                            pctdistance=0.85, startangle=90)
    ax.set_title('训练集构成', fontproperties=FONT, fontsize=13)

    # BR: Test vs Train date range
    ax = axes[1, 1]
    train_dates = train['Date_received'].dropna()
    test_dates = test['Date_received'].dropna()
    if len(train_dates) > 0:
        ax.barh(['训练集\nDate_received', '训练集\nDate', '测试集\nDate_received'],
                [len(train_dates), len(train['Date'].dropna()), len(test_dates)],
                color=['#3b82f6', '#22c55e', '#f59e0b'], height=0.5)
    ax.set_xlabel('记录数', fontproperties=FONT)
    ax.set_title('时间范围覆盖', fontproperties=FONT, fontsize=13)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '01_data_overview')


def chart_redemption_rate(train):
    """Chart 02: Coupon redemption analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('优惠券核销率分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    # Donut chart
    ax = axes[0]
    has_coupon = train['has_coupon'].sum()
    no_coupon = (~train['has_coupon']).sum()
    used = train['is_used'].sum()
    unused = has_coupon - used
    labels = ['仅浏览\n(无券)', '领券未核销', '领券已核销']
    sizes = [no_coupon, unused, used]
    colors = ['#94a3b8', '#f59e0b', '#22c55e']
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors,
        autopct='%1.1f%%', textprops={'fontproperties': FONT, 'fontsize': 11},
        pctdistance=0.78, startangle=90, wedgeprops=dict(width=0.45))
    for t in autotexts:
        t.set_fontproperties(FONT)
        t.set_fontsize(12)
        t.set_color('white')
    ax.set_title('总体构成', fontproperties=FONT, fontsize=13)

    # Redemption rate by discount type
    ax = axes[1]
    coupon_only = train[train['has_coupon']].copy()
    rates = coupon_only.groupby('discount_type')['is_used'].mean() * 100
    rates = rates.reindex(['满减', '折扣'])
    colors = ['#3b82f6', '#f59e0b']
    bars = ax.bar(rates.index, rates.values, color=colors, width=0.5)
    for bar, val in zip(bars, rates.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f'{val:.1f}%', ha='center', va='bottom', fontproperties=FONT, fontsize=12, fontweight='bold')
    ax.set_ylabel('核销率 (%)', fontproperties=FONT)
    ax.set_title('不同折扣类型核销率', fontproperties=FONT, fontsize=13)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '02_coupon_redemption_rate')


def chart_user_behavior(train):
    """Chart 03: User behavior analysis."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('用户行为分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    # Coupons received per user
    ax = axes[0]
    coupon_rows = train[train['has_coupon']]
    coupons_per_user = coupon_rows.groupby('User_id').size()
    ax.hist(np.log1p(coupons_per_user), bins=50, color='#3b82f6', edgecolor='white', alpha=0.8)
    ax.set_xlabel('用户领券数 (log)', fontproperties=FONT)
    ax.set_ylabel('用户数', fontproperties=FONT)
    ax.set_title('用户领券频次分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Coupons used per user
    ax = axes[1]
    used_rows = train[train['is_used']]
    used_per_user = used_rows.groupby('User_id').size()
    ax.hist(np.log1p(used_per_user), bins=50, color='#22c55e', edgecolor='white', alpha=0.8)
    ax.set_xlabel('用户用券数 (log)', fontproperties=FONT)
    ax.set_ylabel('用户数', fontproperties=FONT)
    ax.set_title('用户用券频次分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # User segments
    ax = axes[2]
    user_stats = coupon_rows.groupby('User_id').agg(
        received=('Coupon_id', 'count'),
        used=('is_used', 'sum')
    )
    user_stats['is_collector'] = user_stats['received'] >= 10
    user_stats['is_redeemer'] = user_stats['used'] >= 5
    segments = []
    for _, row in user_stats.iterrows():
        if row['used'] >= 5:
            segments.append('核销用户')
        elif row['received'] >= 10:
            segments.append('领券达人')
        elif row['received'] >= 1:
            segments.append('普通领券')
        else:
            segments.append('纯浏览')
    seg_counts = pd.Series(segments).value_counts()
    seg_order = ['纯浏览', '普通领券', '领券达人', '核销用户']
    seg_counts = seg_counts.reindex(seg_order, fill_value=0)
    colors = ['#94a3b8', '#60a5fa', '#f59e0b', '#22c55e']
    bars = ax.bar(seg_counts.index, seg_counts.values, color=colors, width=0.5)
    for bar, val in zip(bars, seg_counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 500,
                f'{val:,}', ha='center', va='bottom', fontproperties=FONT, fontsize=10)
    ax.set_ylabel('用户数', fontproperties=FONT)
    ax.set_title('用户分群', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)
    ax.tick_params(axis='x', labelrotation=15)

    plt.tight_layout()
    return save_chart(fig, '03_user_behavior')


def chart_merchant_analysis(train):
    """Chart 04: Merchant analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('商户分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    coupon_rows = train[train['has_coupon']].copy()
    merchant_stats = coupon_rows.groupby('Merchant_id').agg(
        coupon_count=('Coupon_id', 'count'),
        redemption_rate=('is_used', 'mean')
    ).reset_index()

    # Top 20 merchants by coupon volume
    ax = axes[0]
    top20 = merchant_stats.nlargest(20, 'coupon_count')
    bars = ax.barh(range(20), top20['coupon_count'].values, color='#3b82f6', height=0.6)
    ax.set_yticks(range(20))
    ax.set_yticklabels([f'商户{i+1}' for i in range(20)], fontproperties=FONT, fontsize=8)
    ax.set_xlabel('优惠券数量', fontproperties=FONT)
    ax.set_title('Top 20 商户优惠券数量', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Coupon count vs redemption rate scatter
    ax = axes[1]
    mask = merchant_stats['coupon_count'] >= 10
    ax.scatter(merchant_stats.loc[mask, 'coupon_count'],
               merchant_stats.loc[mask, 'redemption_rate'] * 100,
               alpha=0.3, s=15, color='#f59e0b', edgecolors='none')
    ax.set_xlabel('优惠券数量 (log)', fontproperties=FONT)
    ax.set_ylabel('核销率 (%)', fontproperties=FONT)
    ax.set_title('商户优惠券数量 vs 核销率', fontproperties=FONT)
    ax.set_xscale('log')
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '04_merchant_analysis')


def chart_discount_analysis(train):
    """Chart 05: Discount rate analysis."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('折扣力度分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    coupon_rows = train[train['has_coupon']].copy()

    # Discount type distribution
    ax = axes[0, 0]
    type_counts = coupon_rows['discount_type'].value_counts()
    colors = ['#3b82f6', '#f59e0b']
    wedges, texts, autotexts = ax.pie(type_counts.values, labels=type_counts.index,
        colors=colors, autopct='%1.1f%%', textprops={'fontproperties': FONT},
        pctdistance=0.75, startangle=90, wedgeprops=dict(width=0.4))
    for t in autotexts:
        t.set_fontproperties(FONT)
        t.set_color('white')
    ax.set_title('折扣类型分布', fontproperties=FONT)

    # Top 15 discount values
    ax = axes[0, 1]
    top_disc = coupon_rows['Discount_rate'].value_counts().head(15)
    bars = ax.barh(range(15), top_disc.values[::-1], color='#3b82f6', height=0.5)
    ax.set_yticks(range(15))
    ax.set_yticklabels(top_disc.index[::-1], fontproperties=FONT, fontsize=10)
    ax.set_xlabel('数量', fontproperties=FONT)
    ax.set_title('Top 15 折扣值分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Redemption rate by discount type
    ax = axes[1, 0]
    rates = coupon_rows.groupby('discount_type')['is_used'].mean() * 100
    rates = rates.reindex(['满减', '折扣'])
    colors = ['#22c55e', '#f59e0b']
    bars = ax.bar(rates.index, rates.values, color=colors, width=0.4)
    for bar, val in zip(bars, rates.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                f'{val:.1f}%', ha='center', va='bottom', fontproperties=FONT, fontsize=12, fontweight='bold')
    ax.set_ylabel('核销率 (%)', fontproperties=FONT)
    ax.set_title('折扣类型核销率', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Redemption rate by discount value bucket
    ax = axes[1, 1]
    coupon_rows['disc_bucket'] = pd.cut(coupon_rows['discount_value'],
        bins=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 1.0],
        labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50%+'])
    bucket_rates = coupon_rows.groupby('disc_bucket', observed=True)['is_used'].mean() * 100
    bars = ax.bar(bucket_rates.index, bucket_rates.values, color='#8b5cf6', width=0.5)
    for bar, val in zip(bars, bucket_rates.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                f'{val:.1f}%', ha='center', va='bottom', fontproperties=FONT, fontsize=11, fontweight='bold')
    ax.set_ylabel('核销率 (%)', fontproperties=FONT)
    ax.set_title('折扣力度区间 vs 核销率', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '05_discount_analysis')


def chart_distance_analysis(train):
    """Chart 06: Distance impact analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('距离影响分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    coupon_rows = train[train['has_coupon']].copy()
    dist_data = coupon_rows[coupon_rows['Distance'].notna()].copy()
    dist_data['Distance'] = dist_data['Distance'].astype(int)

    # Distance distribution
    ax = axes[0]
    dist_counts = dist_data['Distance'].value_counts().sort_index()
    bars = ax.bar(dist_counts.index, dist_counts.values, color='#3b82f6', width=0.7, edgecolor='white')
    for bar, val in zip(bars, dist_counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
                f'{val:,}', ha='center', va='bottom', fontproperties=FONT, fontsize=9)
    ax.set_xlabel('距离 (km)', fontproperties=FONT)
    ax.set_ylabel('优惠券数量', fontproperties=FONT)
    ax.set_title('优惠券距离分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Distance vs redemption rate
    ax = axes[1]
    dist_rates = dist_data.groupby('Distance')['is_used'].mean() * 100
    ax.bar(dist_rates.index, dist_rates.values, color='#e2e8f0', width=0.7, label='优惠券数量', zorder=1)
    ax2 = ax.twinx()
    ax2.plot(dist_rates.index, dist_rates.values, color='#ef4444', marker='o', linewidth=2, markersize=8, zorder=2)
    for x, y in zip(dist_rates.index, dist_rates.values):
        ax2.annotate(f'{y:.1f}%', (x, y), textcoords='offset points',
                     xytext=(0, 10), ha='center', fontproperties=FONT, fontsize=9, color='#ef4444')
    ax.set_xlabel('距离 (km)', fontproperties=FONT)
    ax.set_ylabel('优惠券数量', fontproperties=FONT)
    ax2.set_ylabel('核销率 (%)', fontproperties=FONT, color='#ef4444')
    ax.set_title('距离 vs 核销率', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label, ax2.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '06_distance_analysis')


def chart_time_analysis(train):
    """Chart 07: Time analysis."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('时间特征分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    coupon_rows = train[train['has_coupon']].dropna(subset=['Date_received']).copy()

    # Monthly coupon received
    ax = axes[0]
    monthly = coupon_rows.groupby('month_received').size()
    ax.plot(monthly.index, monthly.values, color='#3b82f6', marker='o', linewidth=2, markersize=8)
    ax.fill_between(monthly.index, monthly.values, alpha=0.2, color='#3b82f6')
    ax.set_xlabel('月份', fontproperties=FONT)
    ax.set_ylabel('领券数量', fontproperties=FONT)
    ax.set_title('月度领券趋势', fontproperties=FONT)
    ax.set_xticks(range(1, 7))
    ax.set_xticklabels([f'{i}月' for i in range(1, 7)], fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Weekday pattern
    ax = axes[1]
    weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    wd_rates = coupon_rows.groupby('weekday_received')['is_used'].mean() * 100
    wd_counts = coupon_rows.groupby('weekday_received').size()
    bars = ax.bar(range(7), [wd_rates.get(i, 0) for i in range(7)],
                  color=['#3b82f6', '#60a5fa', '#93c5fd', '#f59e0b', '#fbbf24', '#22c55e', '#4ade80'], width=0.5)
    for bar, val in zip(bars, [wd_rates.get(i, 0) for i in range(7)]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.15,
                f'{val:.1f}%', ha='center', va='bottom', fontproperties=FONT, fontsize=10, fontweight='bold')
    ax.set_xlabel('星期', fontproperties=FONT)
    ax.set_ylabel('核销率 (%)', fontproperties=FONT)
    ax.set_xticks(range(7))
    ax.set_xticklabels(weekday_names, fontproperties=FONT)
    ax.set_title('星期几核销率', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Days to redemption
    ax = axes[2]
    valid_days = coupon_rows[coupon_rows['days_to_use'].notna() & (coupon_rows['days_to_use'] >= 0)]
    ax.hist(valid_days['days_to_use'], bins=30, color='#22c55e', edgecolor='white', alpha=0.8)
    ax.axvline(x=15, color='#ef4444', linestyle='--', label='15天有效期')
    ax.legend(prop=FONT, loc='upper right')
    ax.set_xlabel('领券到核销天数', fontproperties=FONT)
    ax.set_ylabel('数量', fontproperties=FONT)
    ax.set_title('核销时间分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '07_time_analysis')


def chart_user_merchant(train):
    """Chart 08: User-Merchant cross analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('用户-商户交叉分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    coupon_rows = train[train['has_coupon']].copy()

    # Interaction frequency
    ax = axes[0]
    um_counts = coupon_rows.groupby(['User_id', 'Merchant_id']).size()
    ax.hist(np.log1p(um_counts), bins=50, color='#8b5cf6', edgecolor='white', alpha=0.8)
    ax.set_xlabel('用户-商户交互次数 (log)', fontproperties=FONT)
    ax.set_ylabel('频次', fontproperties=FONT)
    ax.set_title('用户-商户交互频次分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Top user-merchant pairs heatmap
    ax = axes[1]
    top_users = coupon_rows.groupby('User_id').size().nlargest(10).index
    top_merchants = coupon_rows.groupby('Merchant_id').size().nlargest(10).index
    heatmap_data = coupon_rows[coupon_rows['User_id'].isin(top_users) &
                                coupon_rows['Merchant_id'].isin(top_merchants)]
    pivot = heatmap_data.groupby(['User_id', 'Merchant_id']).size().unstack(fill_value=0)
    pivot = pivot.loc[:, pivot.columns.isin(top_merchants)]
    pivot = pivot.loc[pivot.index.isin(top_users), :]
    sns.heatmap(pivot, ax=ax, cmap='YlOrRd', annot=False, cbar=True)
    ax.set_xlabel('商户', fontproperties=FONT)
    ax.set_ylabel('用户', fontproperties=FONT)
    ax.set_title('Top 10 用户-商户交互热力图', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)
    ax.set_xticklabels([f'商户{i+1}' for i in range(len(ax.get_xticklabels()))], fontproperties=FONT, fontsize=8)
    ax.set_yticklabels([f'用户{i+1}' for i in range(len(ax.get_yticklabels()))], fontproperties=FONT, fontsize=8)

    plt.tight_layout()
    return save_chart(fig, '08_user_merchant')


# ============================================================
# 3. Chart Generation - Online Retail Analysis
# ============================================================
def chart_sales_trends(retail):
    """Chart 09: Sales trends."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('销售趋势分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    valid = retail[~retail['is_return'] & ~retail['is_cancellation']]

    # Monthly revenue
    ax = axes[0]
    monthly_rev = valid.groupby('month_year')['Revenue'].sum()
    ax.plot(range(len(monthly_rev)), monthly_rev.values, color='#3b82f6', marker='o', linewidth=2, markersize=6)
    ax.fill_between(range(len(monthly_rev)), monthly_rev.values, alpha=0.15, color='#3b82f6')
    ax.set_xticks(range(len(monthly_rev)))
    ax.set_xticklabels([str(p) for p in monthly_rev.index], fontproperties=FONT, fontsize=8, rotation=45)
    ax.set_xlabel('月份', fontproperties=FONT)
    ax.set_ylabel('月收入', fontproperties=FONT)
    ax.set_title('月度收入趋势', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Order count + avg value
    ax = axes[1]
    monthly_orders = retail[~retail['is_cancellation']].groupby('month_year')['InvoiceNo'].nunique()
    ax.bar(range(len(monthly_orders)), monthly_orders.values, color='#e2e8f0', label='订单数', zorder=1)
    ax2 = ax.twinx()
    avg_vals = valid.groupby('month_year')['Revenue'].mean()
    ax2.plot(range(len(avg_vals)), avg_vals.values, color='#ef4444', marker='s', linewidth=2, zorder=2)
    ax.set_xticks(range(len(monthly_orders)))
    ax.set_xticklabels([str(p) for p in monthly_orders.index], fontproperties=FONT, fontsize=8, rotation=45)
    ax.set_xlabel('月份', fontproperties=FONT)
    ax.set_ylabel('订单数', fontproperties=FONT)
    ax2.set_ylabel('平均订单金额', fontproperties=FONT, color='#ef4444')
    ax.set_title('订单数 & 平均订单金额', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label, ax2.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '09_sales_trends')


def chart_product_analysis(retail):
    """Chart 10: Product analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('产品分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    valid = retail[~retail['is_return'] & ~retail['is_cancellation']]

    # Top 20 products by revenue
    ax = axes[0]
    product_rev = valid.groupby('Description')['Revenue'].sum().nlargest(20)
    bars = ax.barh(range(20), product_rev.values[::-1], color='#3b82f6', height=0.5)
    ax.set_yticks(range(20))
    ax.set_yticklabels(product_rev.index[::-1], fontsize=8)
    ax.set_xlabel('总收入', fontproperties=FONT)
    ax.set_title('Top 20 产品收入', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Price distribution
    ax = axes[1]
    prices = valid[valid['UnitPrice'] > 0]['UnitPrice']
    ax.hist(np.log1p(prices), bins=50, color='#f59e0b', edgecolor='white', alpha=0.8)
    ax.axvline(x=np.log1p(prices.median()), color='#ef4444', linestyle='--', label=f'中位数 {prices.median():.2f}')
    ax.legend(prop=FONT)
    ax.set_xlabel('单价 (log)', fontproperties=FONT)
    ax.set_ylabel('频次', fontproperties=FONT)
    ax.set_title('产品价格分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '10_product_analysis')


def chart_customer_analysis(retail):
    """Chart 11: Customer RFM analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('客户分析 (RFM)', fontsize=16, fontweight='bold', fontproperties=FONT)

    valid = retail[~retail['is_return'] & ~retail['is_cancellation']].copy()
    ref_date = valid['InvoiceDate'].max()

    customer_stats = valid.groupby('CustomerID').agg(
        recency=('InvoiceDate', lambda x: (ref_date - x.max()).days),
        frequency=('InvoiceNo', 'nunique'),
        monetary=('Revenue', 'sum')
    ).dropna()

    # RFM scatter
    ax = axes[0]
    freq_bins = pd.qcut(customer_stats['frequency'], q=5, duplicates='drop')
    scatter = ax.scatter(customer_stats['recency'], customer_stats['monetary'],
                         c=pd.Categorical(freq_bins).codes, cmap='viridis', alpha=0.4, s=15)
    ax.set_xlabel('Recency (距最近购买天数)', fontproperties=FONT)
    ax.set_ylabel('Monetary (总消费金额)', fontproperties=FONT)
    ax.set_title('RFM: 最近消费 vs 总消费', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)
    fig.colorbar(scatter, ax=ax, label='消费频次分位')

    # Customer value distribution
    ax = axes[1]
    ax.hist(np.log1p(customer_stats[customer_stats['monetary'] > 0]['monetary']),
            bins=50, color='#8b5cf6', edgecolor='white', alpha=0.8)
    ax.set_xlabel('客户总消费 (log)', fontproperties=FONT)
    ax.set_ylabel('客户数', fontproperties=FONT)
    ax.set_title('客户价值分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '11_customer_analysis')


def chart_geography(retail):
    """Chart 12: Geographic distribution."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('地理分布分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    valid = retail[~retail['is_return'] & ~retail['is_cancellation']]

    # Top countries
    ax = axes[0]
    country_rev = valid.groupby('Country')['Revenue'].sum().nlargest(10)
    colors = plt.cm.Set2(np.linspace(0, 1, len(country_rev)))
    bars = ax.barh(range(10), country_rev.values[::-1], color=colors[::-1], height=0.6)
    ax.set_yticks(range(10))
    ax.set_yticklabels(country_rev.index[::-1], fontproperties=FONT, fontsize=10)
    ax.set_xlabel('总收入', fontproperties=FONT)
    ax.set_title('Top 10 国家收入', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # UK vs International
    ax = axes[1]
    uk = valid[valid['Country'] == 'United Kingdom']['Revenue'].sum()
    intl = valid[valid['Country'] != 'United Kingdom']['Revenue'].sum()
    wedges, texts, autotexts = ax.pie([uk, intl], labels=['英国', '其他国家'],
        colors=['#3b82f6', '#f59e0b'], autopct='%1.1f%%',
        textprops={'fontproperties': FONT}, pctdistance=0.75, startangle=90,
        wedgeprops=dict(width=0.45))
    for t in autotexts:
        t.set_fontproperties(FONT)
        t.set_color('white')
    ax.set_title('英国 vs 国际市场占比', fontproperties=FONT)

    plt.tight_layout()
    return save_chart(fig, '12_geography')


def chart_returns_analysis(retail):
    """Chart 13: Returns analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('退货与取消分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    returns = retail[retail['is_return'] | retail['is_cancellation']]

    # Monthly returns
    ax = axes[0]
    monthly_returns = returns.groupby('month_year').size()
    ax.bar(range(len(monthly_returns)), monthly_returns.values, color='#ef4444', alpha=0.7)
    ax.set_xticks(range(len(monthly_returns)))
    ax.set_xticklabels([str(p) for p in monthly_returns.index], fontproperties=FONT, fontsize=8, rotation=45)
    ax.set_xlabel('月份', fontproperties=FONT)
    ax.set_ylabel('退货/取消数量', fontproperties=FONT)
    ax.set_title('月度退货/取消数量', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Return rate over time
    ax = axes[1]
    monthly_total = retail.groupby('month_year').size()
    monthly_return_rate = (monthly_returns / monthly_total * 100).dropna()
    ax.plot(range(len(monthly_return_rate)), monthly_return_rate.values,
            color='#ef4444', marker='o', linewidth=2)
    ax.fill_between(range(len(monthly_return_rate)), monthly_return_rate.values,
                    alpha=0.2, color='#ef4444')
    ax.set_xticks(range(len(monthly_return_rate)))
    ax.set_xticklabels([str(p) for p in monthly_return_rate.index], fontproperties=FONT, fontsize=8, rotation=45)
    ax.set_xlabel('月份', fontproperties=FONT)
    ax.set_ylabel('退货率 (%)', fontproperties=FONT)
    ax.set_title('退货率趋势', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '13_returns_analysis')


def chart_order_value(retail):
    """Chart 14: Order value analysis."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle('订单价值分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    valid = retail[~retail['is_return'] & ~retail['is_cancellation']]
    order_values = valid.groupby('InvoiceNo')['Revenue'].sum()
    order_values = order_values[order_values > 0]
    p99 = order_values.quantile(0.99)
    order_values = order_values[order_values <= p99]

    # Order value distribution
    ax = axes[0]
    ax.hist(np.log1p(order_values), bins=50, color='#3b82f6', edgecolor='white', alpha=0.8)
    ax.axvline(x=np.log1p(order_values.mean()), color='#ef4444', linestyle='--',
               label=f'均值 {order_values.mean():.2f}')
    ax.axvline(x=np.log1p(order_values.median()), color='#22c55e', linestyle='--',
               label=f'中位数 {order_values.median():.2f}')
    ax.legend(prop=FONT)
    ax.set_xlabel('订单金额 (log)', fontproperties=FONT)
    ax.set_ylabel('订单数', fontproperties=FONT)
    ax.set_title('订单金额分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Basket size distribution
    ax = axes[1]
    basket_sizes = valid.groupby('InvoiceNo')['Quantity'].sum()
    basket_sizes = basket_sizes[basket_sizes > 0]
    p99b = basket_sizes.quantile(0.99)
    basket_sizes = basket_sizes[basket_sizes <= p99b]
    ax.hist(basket_sizes, bins=50, color='#f59e0b', edgecolor='white', alpha=0.8)
    ax.axvline(x=basket_sizes.mean(), color='#ef4444', linestyle='--',
               label=f'均值 {basket_sizes.mean():.1f}')
    ax.legend(prop=FONT)
    ax.set_xlabel('订单商品数量', fontproperties=FONT)
    ax.set_ylabel('订单数', fontproperties=FONT)
    ax.set_title('订单商品数量分布', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '14_order_value')


def chart_channel_comparison(train, retail):
    """Chart 15: Cross-channel comparison."""
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle('跨渠道对比分析', fontsize=16, fontweight='bold', fontproperties=FONT)

    # User engagement comparison
    ax = axes[0]
    o2o_users = train.groupby('User_id').size()
    retail_customers = retail[retail['CustomerID'].notna()].groupby('CustomerID').size()
    ax.hist(np.log1p(o2o_users), bins=40, alpha=0.6, label='O2O用户', color='#3b82f6', density=True)
    ax.hist(np.log1p(retail_customers), bins=40, alpha=0.6, label='零售客户', color='#f59e0b', density=True)
    ax.set_xlabel('交互次数 (log)', fontproperties=FONT)
    ax.set_ylabel('密度', fontproperties=FONT)
    ax.set_title('用户交互频次对比', fontproperties=FONT)
    ax.legend(prop=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Key metrics comparison
    ax = axes[1]
    o2o_coupon = train[train['has_coupon']]
    metrics = ['总记录数', '独立用户', '独立商户/产品', '平均折扣力度']
    o2o_vals = [len(train), train['User_id'].nunique(),
                train['Merchant_id'].nunique(),
                o2o_coupon['discount_value'].mean() * 100]
    retail_vals = [len(retail), retail['CustomerID'].dropna().nunique(),
                   retail['StockCode'].nunique(),
                   0]
    x = np.arange(len(metrics))
    ax.bar(x - 0.2, o2o_vals, width=0.4, label='O2O', color='#3b82f6')
    ax.bar(x + 0.2, [retail_vals[0]/1000, retail_vals[1], retail_vals[2], 0],
           width=0.4, label='在线零售', color='#f59e0b')
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontproperties=FONT, fontsize=10)
    ax.set_ylabel('数值', fontproperties=FONT)
    ax.set_title('核心指标对比', fontproperties=FONT)
    ax.legend(prop=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    # Conversion/Return rates
    ax = axes[2]
    o2o_rate = o2o_coupon['is_used'].mean() * 100
    retail_return = retail['is_return'].mean() * 100
    labels = ['O2O核销率', '零售退货率']
    rates = [o2o_rate, retail_return]
    colors = ['#22c55e', '#ef4444']
    bars = ax.bar(labels, rates, color=colors, width=0.5)
    for bar, val in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{val:.1f}%', ha='center', va='bottom', fontproperties=FONT, fontsize=12, fontweight='bold')
    ax.set_ylabel('百分比 (%)', fontproperties=FONT)
    ax.set_title('核销率 vs 退货率', fontproperties=FONT)
    for item in [ax.title, ax.xaxis.label, ax.yaxis.label]:
        item.set_fontproperties(FONT)

    plt.tight_layout()
    return save_chart(fig, '15_channel_comparison')


# ============================================================
# 4. Compute Statistics
# ============================================================
def compute_stats(train, test, retail):
    """Compute all statistics for the HTML report."""
    stats = {}

    # O2O overview
    stats['o2o_train_rows'] = f'{len(train):,}'
    stats['o2o_test_rows'] = f'{len(test):,}'
    stats['o2o_train_cols'] = str(len(train.columns))
    stats['o2o_test_cols'] = str(len(test.columns))
    stats['o2o_users'] = f"{train['User_id'].nunique():,}"
    stats['o2o_merchants'] = f"{train['Merchant_id'].nunique():,}"
    stats['o2o_date_range_train'] = f"{train['Date_received'].min().strftime('%Y-%m-%d')} ~ {train['Date_received'].max().strftime('%Y-%m-%d')}"
    stats['o2o_date_range_test'] = f"{test['Date_received'].min().strftime('%Y-%m-%d')} ~ {test['Date_received'].max().strftime('%Y-%m-%d')}"

    # Redemption
    coupon_rows = train[train['has_coupon']]
    used = coupon_rows['is_used'].sum()
    total_coupons = len(coupon_rows)
    stats['redemption_rate'] = f'{used/total_coupons*100:.1f}%'
    stats['coupon_used'] = f'{int(used):,}'
    stats['coupon_unused'] = f'{int(total_coupons - used):,}'
    stats['coupon_total'] = f'{total_coupons:,}'
    stats['no_coupon'] = f'{int((~train["has_coupon"]).sum()):,}'

    # Discount types
    manjian = (coupon_rows['discount_type'] == '满减').sum()
    zhekou = (coupon_rows['discount_type'] == '折扣').sum()
    stats['manjian_count'] = f'{int(manjian):,}'
    stats['zhekou_count'] = f'{int(zhekou):,}'
    stats['manjian_pct'] = f'{manjian/total_coupons*100:.1f}%'
    stats['zhekou_pct'] = f'{zhekou/total_coupons*100:.1f}%'
    mj_rate = coupon_rows[coupon_rows['discount_type'] == '满减']['is_used'].mean() * 100
    zk_rate = coupon_rows[coupon_rows['discount_type'] == '折扣']['is_used'].mean() * 100
    stats['manjian_redemption'] = f'{mj_rate:.1f}%'
    stats['zhekou_redemption'] = f'{zk_rate:.1f}%'

    # Distance
    dist_data = coupon_rows[coupon_rows['Distance'].notna()].copy()
    dist_data['Distance'] = dist_data['Distance'].astype(int)
    dist_0 = (dist_data['Distance'] == 0).sum()
    stats['dist_0_count'] = f'{int(dist_0):,}'
    dist_0_rate = dist_data[dist_data['Distance'] == 0]['is_used'].mean() * 100
    dist_10_rate = dist_data[dist_data['Distance'] == 10]['is_used'].mean() * 100
    stats['dist_0_redemption'] = f'{dist_0_rate:.1f}%'
    stats['dist_10_redemption'] = f'{dist_10_rate:.1f}%'

    # User segments
    user_stats = coupon_rows.groupby('User_id').agg(
        received=('Coupon_id', 'count'), used=('is_used', 'sum')
    )
    n_redeemers = (user_stats['used'] >= 5).sum()
    n_collectors = ((user_stats['received'] >= 10) & (user_stats['used'] < 5)).sum()
    n_normal = ((user_stats['received'] >= 1) & (user_stats['received'] < 10) & (user_stats['used'] < 5)).sum()
    stats['n_redeemers'] = f'{int(n_redeemers):,}'
    stats['n_collectors'] = f'{int(n_collectors):,}'
    stats['n_normal'] = f'{int(n_normal):,}'

    # Online Retail
    valid = retail[~retail['is_return'] & ~retail['is_cancellation']]
    stats['retail_rows'] = f'{len(retail):,}'
    stats['retail_invoices'] = f"{retail['InvoiceNo'].nunique():,}"
    stats['retail_products'] = f"{retail['StockCode'].nunique():,}"
    stats['retail_customers'] = f"{retail['CustomerID'].dropna().nunique():,}"
    stats['retail_countries'] = f"{retail['Country'].nunique()}"
    stats['retail_revenue'] = f'{valid["Revenue"].sum():,.0f}'
    stats['retail_avg_order'] = f'{valid.groupby("InvoiceNo")["Revenue"].sum().mean():.2f}'
    stats['retail_return_rate'] = f'{retail["is_return"].mean()*100:.1f}%'
    stats['retail_date_range'] = f"{retail['InvoiceDate'].min().strftime('%Y-%m-%d')} ~ {retail['InvoiceDate'].max().strftime('%Y-%m-%d')}"

    # Key insights
    stats['insights'] = [
        f'O2O优惠券总体核销率仅 {stats["redemption_rate"]}，存在严重的正负样本不平衡问题',
        f'满减券占比 {stats["manjian_pct"]}，核销率 {stats["manjian_redemption"]}；折扣券占比 {stats["zhekou_pct"]}，核销率 {stats["zhekou_redemption"]}',
        f'核销用户仅 {stats["n_redeemers"]} 人，大多数用户领券后未使用',
        f'在线零售覆盖 {stats["retail_countries"]} 个国家，{stats["retail_customers"]} 位客户，总收入 {stats["retail_revenue"]}',
        f'在线零售退货率 {stats["retail_return_rate"]}，需关注异常订单模式',
        f'O2O数据时间跨度为2016年1-7月，在线零售为2010年12月-2011年12月'
    ]

    return stats


# ============================================================
# 5. HTML Report Generation
# ============================================================
def generate_html_report(stats, charts):
    """Generate the final HTML report."""
    template = Template('''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>O2O优惠券与在线零售数据分析报告</title>
    <style>
        :root {
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --text-secondary: #64748b;
            --primary: #3b82f6;
            --accent: #f59e0b;
            --success: #22c55e;
            --danger: #ef4444;
            --border: #e2e8f0;
            --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, "Noto Sans SC", "Microsoft YaHei", "PingFang SC", sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.7;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        .header {
            text-align: center;
            padding: 3rem 0 2rem;
            border-bottom: 2px solid var(--border);
            margin-bottom: 2rem;
        }
        .header h1 { font-size: 2rem; font-weight: 700; color: var(--primary); margin-bottom: 0.5rem; }
        .header .subtitle { color: var(--text-secondary); font-size: 0.95rem; }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 2rem 0;
        }
        .stat-card {
            background: var(--card);
            border-radius: 12px;
            padding: 1.25rem;
            box-shadow: var(--shadow);
            text-align: center;
            border-top: 3px solid var(--primary);
        }
        .stat-card .value { font-size: 1.8rem; font-weight: 700; color: var(--primary); }
        .stat-card .label { font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem; }

        .section { margin: 3rem 0; }
        .section-title {
            font-size: 1.4rem;
            color: var(--primary);
            border-left: 4px solid var(--primary);
            padding-left: 1rem;
            margin-bottom: 1.5rem;
            font-weight: 600;
        }

        .card {
            background: var(--card);
            border-radius: 12px;
            box-shadow: var(--shadow);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .card h3 { font-size: 1.1rem; margin-bottom: 1rem; color: var(--text); }
        .chart-card { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
        .chart-card img { width: 100%; border-radius: 8px; }

        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.65rem 0.75rem; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: #f1f5f9; font-weight: 600; font-size: 0.9rem; }
        td { font-size: 0.9rem; }
        tr:hover { background: #f8fafc; }

        .insight-box {
            background: #eff6ff;
            border-left: 4px solid var(--primary);
            padding: 1rem 1.25rem;
            border-radius: 0 8px 8px 0;
            margin: 0.5rem 0;
        }
        .insight-box ul { padding-left: 1.25rem; }
        .insight-box li { margin: 0.3rem 0; font-size: 0.95rem; }

        .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .metric { padding: 0.5rem 0; }
        .metric .m-label { color: var(--text-secondary); font-size: 0.85rem; }
        .metric .m-value { font-size: 1.2rem; font-weight: 600; color: var(--text); }

        footer {
            text-align: center;
            padding: 2rem 0;
            color: var(--text-secondary);
            border-top: 1px solid var(--border);
            margin-top: 2rem;
            font-size: 0.85rem;
        }

        @media (max-width: 768px) {
            .chart-card { grid-template-columns: 1fr; }
            .two-col { grid-template-columns: 1fr; }
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
        }
    </style>
</head>
<body>
<div class="container">
    <!-- Header -->
    <div class="header">
        <h1>O2O优惠券与在线零售数据分析报告</h1>
        <p class="subtitle">生成日期：{{ generated_date }} | 数据来源：天池O2O竞赛 + UCI在线零售</p>
    </div>

    <!-- Key Stats -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="value">{{ stats.o2o_train_rows }}</div>
            <div class="label">O2O训练集记录数</div>
        </div>
        <div class="stat-card">
            <div class="value">{{ stats.o2o_test_rows }}</div>
            <div class="label">O2O测试集记录数</div>
        </div>
        <div class="stat-card" style="border-top-color: var(--success);">
            <div class="value" style="color: var(--success);">{{ stats.redemption_rate }}</div>
            <div class="label">优惠券核销率</div>
        </div>
        <div class="stat-card">
            <div class="value">{{ stats.o2o_users }}</div>
            <div class="label">O2O独立用户数</div>
        </div>
        <div class="stat-card">
            <div class="value">{{ stats.retail_rows }}</div>
            <div class="label">在线零售交易数</div>
        </div>
        <div class="stat-card" style="border-top-color: var(--accent);">
            <div class="value" style="color: var(--accent);">{{ stats.retail_revenue }}</div>
            <div class="label">在线零售总收入</div>
        </div>
    </div>

    <!-- Insights -->
    <div class="card">
        <h3>核心发现</h3>
        <div class="insight-box">
            <ul>
                {% for insight in stats.insights %}
                <li>{{ insight }}</li>
                {% endfor %}
            </ul>
        </div>
    </div>

    <!-- Section 1: O2O Overview -->
    <div class="section">
        <h2 class="section-title">一、O2O优惠券数据概览</h2>
        <div class="chart-card">
            <div class="card">
                <img src="{{ charts.data_overview }}" alt="数据概览">
            </div>
            <div class="card">
                <h3>基本统计</h3>
                <table>
                    <tr><th>指标</th><th>训练集</th><th>测试集</th></tr>
                    <tr><td>记录数</td><td>{{ stats.o2o_train_rows }}</td><td>{{ stats.o2o_test_rows }}</td></tr>
                    <tr><td>独立用户数</td><td colspan="2">{{ stats.o2o_users }}</td></tr>
                    <tr><td>独立商户数</td><td colspan="2">{{ stats.o2o_merchants }}</td></tr>
                    <tr><td>时间范围</td><td>{{ stats.o2o_date_range_train }}</td><td>{{ stats.o2o_date_range_test }}</td></tr>
                </table>
            </div>
        </div>
    </div>

    <!-- Section 2: Redemption -->
    <div class="section">
        <h2 class="section-title">二、优惠券核销率分析</h2>
        <div class="chart-card">
            <div class="card">
                <img src="{{ charts.redemption }}" alt="核销率分析">
            </div>
            <div class="card">
                <h3>核销详情</h3>
                <table>
                    <tr><th>类别</th><th>数量</th></tr>
                    <tr><td>领券总数</td><td>{{ stats.coupon_total }}</td></tr>
                    <tr><td>已核销</td><td>{{ stats.coupon_used }}</td></tr>
                    <tr><td>未核销</td><td>{{ stats.coupon_unused }}</td></tr>
                    <tr><td>无券浏览</td><td>{{ stats.no_coupon }}</td></tr>
                    <tr><td><b>核销率</b></td><td><b style="color:var(--success)">{{ stats.redemption_rate }}</b></td></tr>
                </table>
            </div>
        </div>
    </div>

    <!-- Section 3: User Behavior -->
    <div class="section">
        <h2 class="section-title">三、用户行为分析</h2>
        <div class="card">
            <img src="{{ charts.user_behavior }}" alt="用户行为" style="width:100%;border-radius:8px;">
        </div>
        <div class="card">
            <table>
                <tr><th>用户分群</th><th>数量</th></tr>
                <tr><td>核销用户（用券5+）</td><td>{{ stats.n_redeemers }}</td></tr>
                <tr><td>领券达人（领券10+，核销<5）</td><td>{{ stats.n_collectors }}</td></tr>
                <tr><td>普通领券用户</td><td>{{ stats.n_normal }}</td></tr>
            </table>
        </div>
    </div>

    <!-- Section 4: Merchant -->
    <div class="section">
        <h2 class="section-title">四、商户分析</h2>
        <div class="card">
            <img src="{{ charts.merchant }}" alt="商户分析" style="width:100%;border-radius:8px;">
        </div>
    </div>

    <!-- Section 5: Discount -->
    <div class="section">
        <h2 class="section-title">五、折扣力度分析</h2>
        <div class="chart-card">
            <div class="card">
                <img src="{{ charts.discount }}" alt="折扣分析">
            </div>
            <div class="card">
                <h3>折扣类型对比</h3>
                <table>
                    <tr><th>类型</th><th>数量</th><th>占比</th><th>核销率</th></tr>
                    <tr><td>满减券</td><td>{{ stats.manjian_count }}</td><td>{{ stats.manjian_pct }}</td><td>{{ stats.manjian_redemption }}</td></tr>
                    <tr><td>折扣券</td><td>{{ stats.zhekou_count }}</td><td>{{ stats.zhekou_pct }}</td><td>{{ stats.zhekou_redemption }}</td></tr>
                </table>
            </div>
        </div>
    </div>

    <!-- Section 6: Distance -->
    <div class="section">
        <h2 class="section-title">六、距离影响分析</h2>
        <div class="card">
            <img src="{{ charts.distance }}" alt="距离分析" style="width:100%;border-radius:8px;">
        </div>
        <div class="card">
            <div class="two-col">
                <div class="metric">
                    <div class="m-label">距离0km核销率</div>
                    <div class="m-value">{{ stats.dist_0_redemption }}</div>
                </div>
                <div class="metric">
                    <div class="m-label">距离10km核销率</div>
                    <div class="m-value">{{ stats.dist_10_redemption }}</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Section 7: Time -->
    <div class="section">
        <h2 class="section-title">七、时间特征分析</h2>
        <div class="card">
            <img src="{{ charts.time }}" alt="时间分析" style="width:100%;border-radius:8px;">
        </div>
    </div>

    <!-- Section 8: User-Merchant -->
    <div class="section">
        <h2 class="section-title">八、用户-商户交叉分析</h2>
        <div class="card">
            <img src="{{ charts.user_merchant }}" alt="用户-商户分析" style="width:100%;border-radius:8px;">
        </div>
    </div>

    <!-- Section 9: Sales Trends -->
    <div class="section">
        <h2 class="section-title">九、在线零售销售趋势</h2>
        <div class="card">
            <img src="{{ charts.sales_trends }}" alt="销售趋势" style="width:100%;border-radius:8px;">
        </div>
    </div>

    <!-- Section 10: Products -->
    <div class="section">
        <h2 class="section-title">十、在线零售产品与客户</h2>
        <div class="chart-card">
            <div class="card">
                <img src="{{ charts.products }}" alt="产品分析">
            </div>
            <div class="card">
                <img src="{{ charts.customers }}" alt="客户分析">
            </div>
        </div>
    </div>

    <!-- Section 11: Geography -->
    <div class="section">
        <h2 class="section-title">十一、地理分布与退货分析</h2>
        <div class="chart-card">
            <div class="card">
                <img src="{{ charts.geography }}" alt="地理分布">
            </div>
            <div class="card">
                <img src="{{ charts.returns }}" alt="退货分析">
            </div>
        </div>
    </div>

    <!-- Section 12: Order Value -->
    <div class="section">
        <h2 class="section-title">十二、在线零售订单价值</h2>
        <div class="card">
            <img src="{{ charts.order_value }}" alt="订单价值" style="width:100%;border-radius:8px;">
        </div>
        <div class="card">
            <h3>在线零售统计</h3>
            <table>
                <tr><th>指标</th><th>值</th></tr>
                <tr><td>交易记录数</td><td>{{ stats.retail_rows }}</td></tr>
                <tr><td>独立订单数</td><td>{{ stats.retail_invoices }}</td></tr>
                <tr><td>独立产品数</td><td>{{ stats.retail_products }}</td></tr>
                <tr><td>独立客户数</td><td>{{ stats.retail_customers }}</td></tr>
                <tr><td>覆盖国家数</td><td>{{ stats.retail_countries }}</td></tr>
                <tr><td>总收入</td><td>{{ stats.retail_revenue }}</td></tr>
                <tr><td>平均订单金额</td><td>{{ stats.retail_avg_order }}</td></tr>
                <tr><td>退货率</td><td>{{ stats.retail_return_rate }}</td></tr>
                <tr><td>时间范围</td><td>{{ stats.retail_date_range }}</td></tr>
            </table>
        </div>
    </div>

    <!-- Section 13: Cross-Channel -->
    <div class="section">
        <h2 class="section-title">十三、跨渠道对比分析</h2>
        <div class="card">
            <img src="{{ charts.channel }}" alt="跨渠道对比" style="width:100%;border-radius:8px;">
        </div>
    </div>

    <footer>
        <p>数据来源：阿里云天池 O2O优惠券预测竞赛 | UCI Machine Learning Repository - Online Retail</p>
        <p>报告生成于 {{ generated_date }}</p>
    </footer>
</div>
</body>
</html>''')

    html = template.render(
        generated_date=datetime.now().strftime('%Y-%m-%d %H:%M'),
        stats=stats,
        charts=charts
    )

    report_path = HTML_DIR / 'report.html'
    report_path.write_text(html, encoding='utf-8')
    print(f'HTML report saved to: {report_path}')
    return report_path


# ============================================================
# Main
# ============================================================
def main():
    print('=' * 60)
    print('O2O Coupon + Online Retail Data Analysis')
    print('=' * 60)

    # Load data
    train = load_offline_train()
    test = load_offline_test()
    retail = load_online_retail()

    print(f'Train: {len(train):,} rows, {len(train.columns)} cols')
    print(f'Test: {len(test):,} rows, {len(test.columns)} cols')
    print(f'Retail: {len(retail):,} rows, {len(retail.columns)} cols')

    # Generate charts
    print('\nGenerating charts...')
    charts = {}
    charts['data_overview'] = chart_data_overview(train, test)
    print('  [1/15] Data overview')
    charts['redemption'] = chart_redemption_rate(train)
    print('  [2/15] Redemption rate')
    charts['user_behavior'] = chart_user_behavior(train)
    print('  [3/15] User behavior')
    charts['merchant'] = chart_merchant_analysis(train)
    print('  [4/15] Merchant analysis')
    charts['discount'] = chart_discount_analysis(train)
    print('  [5/15] Discount analysis')
    charts['distance'] = chart_distance_analysis(train)
    print('  [6/15] Distance analysis')
    charts['time'] = chart_time_analysis(train)
    print('  [7/15] Time analysis')
    charts['user_merchant'] = chart_user_merchant(train)
    print('  [8/15] User-merchant cross')
    charts['sales_trends'] = chart_sales_trends(retail)
    print('  [9/15] Sales trends')
    charts['products'] = chart_product_analysis(retail)
    print('  [10/15] Product analysis')
    charts['customers'] = chart_customer_analysis(retail)
    print('  [11/15] Customer RFM')
    charts['geography'] = chart_geography(retail)
    print('  [12/15] Geography')
    charts['returns'] = chart_returns_analysis(retail)
    print('  [13/15] Returns')
    charts['order_value'] = chart_order_value(retail)
    print('  [14/15] Order value')
    charts['channel'] = chart_channel_comparison(train, retail)
    print('  [15/15] Channel comparison')

    # Compute statistics
    print('\nComputing statistics...')
    stats = compute_stats(train, test, retail)

    # Generate HTML report
    print('\nGenerating HTML report...')
    generate_html_report(stats, charts)

    # Summary
    chart_files = list(CHARTS_DIR.glob('*.png'))
    print(f'\nDone! Generated {len(chart_files)} charts and 1 HTML report.')
    print(f'Charts: {CHARTS_DIR}')
    print(f'Report: {HTML_DIR / "report.html"}')


if __name__ == '__main__':
    main()
