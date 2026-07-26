#import necessary libraries
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sys
import re
import datetime as dt
from scipy import stats
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.stattools import kpss
sys.path.append('../../templates/')
from plot_creator import lineplot 

def load_and_clean_data(filepath,regex_pattern):
    """Loads the data from the csv's and uses regex to change column names to more convenient"""
    df = pd.read_csv(filepath)
    df['DATE'] = pd.to_datetime(df['DATE'])

    #rename columns using regex
    cols = {}
    for col in df.columns:
        match = re.search(regex_pattern,col)
        if match:
            cols[col] = match.group(1) 
        else:
            cols[col] = col

    df.rename(columns=cols, inplace=True)
    return df.fillna(0)
def find_matching_period(dfs,column):
    '''Finds the periods that overlap between the dfs provided, then returns said dfs as copies within the matching timeframe.'''
    matched = []
    p1 = max(df[column].min() for df in dfs)
    p2 = min(df[column].max() for df in dfs)

    for i in range(len(dfs)):
        mask = ((dfs[i][column] >= p1) & (dfs[i][column] <= p2))
        matched.append(dfs[i][mask].copy())

    return matched
def rolling_pearson(df1,df2,interval=12):
    '''Calculates rolling pearson correlation for set intervals of time, the dfs must be of equal length'''
    pearson_results = df1.rolling(window=interval).corr(df2)
    return pearson_results
def print_stationarity_table(hhi_raw_adf, hhi_raw_kpss, bs_raw_adf, bs_raw_kpss,hhi_diff_adf, hhi_diff_kpss, bs_diff_adf, bs_diff_kpss):
    """Prints full stationarity test results with 5% critical values formatted as a Markdown table."""    
    # Extract 5% critical values directly from statmodels output dicts
    adf_cv_5pct = hhi_raw_adf[4]['5%']
    kpss_cv_5pct = hhi_raw_kpss[3]['5%']

    table = f"""
### Stationarity Test Results (ADF & KPSS)

| Variable | Transformation | ADF Stat | ADF p-val | ADF 5% CV | KPSS Stat | KPSS p-val | KPSS 5% CV | Decision |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Total HHI** | Raw Levels $I(1)$ | {hhi_raw_adf[0]:.4f} | {hhi_raw_adf[1]:.4f} | {adf_cv_5pct:.4f} | {hhi_raw_kpss[0]:.4f} | {hhi_raw_kpss[1]:.4f} | {kpss_cv_5pct:.4f} | Non-Stationary |
| **Yield Spread** | Raw Levels $I(1)$ | {bs_raw_adf[0]:.4f} | {bs_raw_adf[1]:.4f} | {adf_cv_5pct:.4f} | {bs_raw_kpss[0]:.4f} | {bs_raw_kpss[1]:.4f} | {kpss_cv_5pct:.4f} | Non-Stationary |
| **Total HHI** | First Diff $\Delta I(0)$ | {hhi_diff_adf[0]:.4f} | {hhi_diff_adf[1]:.4f} | {adf_cv_5pct:.4f} | {hhi_diff_kpss[0]:.4f} | {hhi_diff_kpss[1]:.4f} | {kpss_cv_5pct:.4f} | **Stationary** |
| **Yield Spread** | First Diff $\Delta I(0)$ | {bs_diff_adf[0]:.4f} | {bs_diff_adf[1]:.4f} | {adf_cv_5pct:.4f} | {bs_diff_kpss[0]:.4f} | {bs_diff_kpss[1]:.4f} | {kpss_cv_5pct:.4f} | **Stationary** |

"""
    print(table)
def main():
    #set the style
    plt.style.use('./econ_style.mplstyle')

    #load data for HHI and for bond spread
    hhi_re = r'TGB\.M\.([A-Z0-9]{2})'
    bond_re = r'IRS\.M\.([A-Z0-9]{2})\.L\.L40\.CI\.0000\.EUR\.N\.Z'
    raw_HHI = load_and_clean_data('./data/ECB Data Portal_20260705000624.csv', hhi_re)
    raw_bond_rates = load_and_clean_data('./data/ECB Data Portal_20260706200507.csv', bond_re)
    #convert str to datetime
    raw_HHI['DATE'] = pd.to_datetime(raw_HHI['DATE'])
    raw_bond_rates['DATE'] = pd.to_datetime(raw_bond_rates['DATE'])

    #find overlapping periods and use them 
    dfs = [raw_HHI.reset_index(),raw_bond_rates.reset_index()]
    raw_HHI,raw_bond_rates = find_matching_period(dfs,'DATE')
    raw_HHI.set_index('DATE',inplace=True)
    raw_bond_rates.set_index('DATE',inplace=True)

    #select countries used for analysis
    cols_shared = ['DE','LU','NL','ES','IT']
    
    #clip lower values (HHI uses squared share of the market so it would distort the results)
    trimmed_HHI = raw_HHI[cols_shared].copy()
    df_HHI = trimmed_HHI.clip(lower=0)

    #Calculate HHI
    df_HHI['TOTAL_VALUE'] = df_HHI[cols_shared].sum(axis=1)
    df_HHI[cols_shared] = df_HHI[cols_shared].div(df_HHI['TOTAL_VALUE'],axis=0).pow(2).multiply(10000,axis=0)
    df_HHI['TOTAL_HHI'] = df_HHI[cols_shared].sum(axis=1)

    #Calculate Bond spread between the italian and german bonds
    df_bond_rates = raw_bond_rates.drop(columns=['TIME PERIOD']).copy()
    df_bond_rates['BOND_SPREAD'] = df_bond_rates['IT'] - df_bond_rates['DE']

    #create a new cutoff period for ADF
    start_date = '2005-01-31'
    t_HHI = df_HHI['TOTAL_HHI'].loc[start_date:]
    t_BS = df_bond_rates['BOND_SPREAD'].loc[start_date:]

    t_HHI_differentiated = t_HHI.diff().dropna()
    t_BS_differentiated = t_BS.diff().dropna()
    #check stationarity for non-differenced data
    result_HHI_adf = adfuller(t_HHI,autolag='AIC')
    result_BS_adf = adfuller(t_BS,autolag='AIC')
    results_HHI_kpss = kpss(t_HHI,regression='c')
    results_BS_kpss = kpss(t_BS,regression='c')


    #check stationarity for differenced data
    result_HHI_differentiated_adf = adfuller(t_HHI_differentiated,autolag='AIC')
    result_BS_differentiated_adf = adfuller(t_BS_differentiated,autolag='AIC')
    results_HHI_differentiated_kpss = kpss(t_HHI_differentiated,regression='c')
    results_BS_differentiated_kpss = kpss(t_BS_differentiated,regression='c')  

    # Print Markdown table for README
    print_stationarity_table(
        result_HHI_adf, results_HHI_kpss,
        result_BS_adf, results_BS_kpss,
        result_HHI_differentiated_adf, results_HHI_differentiated_kpss,
        result_BS_differentiated_adf, results_BS_differentiated_kpss
    )

    #calculate pearson for the analysed bond spread and HHI index
    rp_non_stationary = rolling_pearson(t_BS,t_HHI,36)
    rp_stationary = rolling_pearson(t_BS_differentiated,t_HHI_differentiated,36)

    #prepare the data for visualization
    cols_BS = ['DE','IT']

    bs_IT_DE = lineplot(raw_bond_rates.reset_index(),['DATE'],cols_BS,stack=True,stack_title='Bond yield difference between Italian and German bonds')
    bs_IT_DE.axes[0].axvspan(dt.datetime(2008,1,31),dt.datetime(2009,6,30),color="#81268A",alpha=0.3,label='Eurozone recession')
    bs_IT_DE.axes[0].axvspan(dt.datetime(2011,7,31),dt.datetime(2013,3,31),color="#81268A",alpha=0.3)
    bs_IT_DE.axes[0].fill_between(raw_bond_rates.reset_index()['DATE'],raw_bond_rates['DE'],raw_bond_rates['IT'],alpha=0.5,color='#EFBCD5',label='Yield spread')
    bs_IT_DE.axes[0].set_prop_cycle(plt.rcParams['axes.prop_cycle'])
    bs_IT_DE.axes[0].set_ylabel('Bond Yield (%)')
    bs_IT_DE.axes[0].set_xlabel('Year')
    bs_IT_DE.axes[0].legend()
    bs_IT_DE.savefig('./charts/bond_spread_Germany_Italy.png')
    plt.close(bs_IT_DE)
    #plot HHI against bond spread
    fig,ax1 = plt.subplots()
    ax2 = ax1.twinx()
    p1 = ax2.plot(t_BS.index,t_BS,label='Yield spread')
    p2 = ax1.plot(t_HHI.index,t_HHI,color='#C0504D',label='HHI')
    ax1.grid(visible=False)
    lines = p1 + p2
    labels = [l.get_label() for l in lines]
    ax1.legend(lines,labels)
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Total HHI')
    ax2.set_ylabel('Yield Spread (%)')
    ax1.set_title('Total HHI vs Yield spread (2005-2026)')
    ax1.set_yticks(np.arange(2000,11000,step=2000))
    fig.savefig('./charts/HHI_vs_Yield.png')
    plt.close(fig)
    #plot differentiated HHI against yield 
    fig,(ax1,ax2) = plt.subplots(1,2,sharex=True,figsize=(14,5))
    
    ax1.plot(t_HHI_differentiated.index,t_HHI_differentiated,color='#C0504D',label='Δ HHI')
    ax1.set_xlabel('Year')
    ax1.set_ylabel('Δ HHI')
    ax1.set_title('Panel A: Δ Total HHI (Month-over-Month)')
    ax2.plot(t_BS_differentiated.index,t_BS_differentiated,label='Δ Yield spread')
    ax2.set_xlabel('Year')
    ax2.set_ylabel('Δ Yield Spread (%)')
    ax2.set_title('Panel B: Δ Total Yield Spread (Month-over-Month)')
    fig.text(0.99,-0.01,"*Differentiation method: t_n - t_(n-1)",ha="right",va="bottom",fontsize=9,color="gray",style="italic")
    fig.savefig('./charts/HHI_vs_Yield_differentiated.png',dpi=300)
    plt.close(fig)
    fig,ax = plt.subplots()

    ax.plot(rp_stationary.index,rp_stationary,label='stationary')
    ax.plot(rp_non_stationary.index,rp_non_stationary,label='non stationary') #color='#d724bf')

    ax.legend()
    ax.set_xlabel(f'Year')
    ax.set_ylabel(f'Pearson\'s correlation coefficient')
    ax.set_title('Rolling Pearson correlation (36-month period) - non-stationary vs stationary')
    fig.savefig('./charts/Rolling_Pearson_Correlation_36month_comparison.png')
    plt.close(fig)
    fig,ax = plt.subplots()

    ax.plot(rp_non_stationary.index,rp_non_stationary)
    ax.set_xlabel(f'Year')
    ax.set_ylabel(f'Pearson\'s correlation coefficient')
    ax.set_title('Rolling Pearson correlation (36-month period) - non-stationary')
    fig.subplots_adjust(bottom=0.15)
    fig.savefig('./charts/Rolling_Pearson_Correlation_36months.png')
    plt.close(fig)
if __name__ == "__main__":
    main()
