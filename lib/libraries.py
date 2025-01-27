#
# Helper functions for spartan supper optimization
#

import sqlite3
import pandas
import pickle
import pandas
import numpy
from deap import base, creator, tools, algorithms
from cvxopt import matrix, solvers # an alternative linear programming library
solvers.options['show_progress'] = False
from sklearn.preprocessing import normalize
from sklearn.cluster import KMeans
import random
from time import time


def load_data():
    # this SQL selects the FOOD_ID, NUTRIENT_ID and AMOUNT and does some manual filtering of things people don't eat
    nutrient_sql="""
    select 
           a.food_id ,a.nutrient_id,a.amount from  nutrition as a
    inner join food as b on
           a.food_id=b.id
    where 
           b.food_group_id not in (200,300,800,1800,2100,2200,3500,3600) -- unappealing groups like baby-food and herbs
           and 
           a.food_id not in (1045,1046,1047,1048,1050,1072,1112,1114,1163,1185,1188,1189,1190, -- these foods are gross, or rare, or otherwise blacklisted
    1191,1192,1193,1194,1200,1215,1226,9001,9059,9061,9062,9086,
    9088,9138,9145,9172,9174,9175,9177,9192,9276,9295,9296,9301,
    9311,9312,9313,9314,9315,9321,9334,9426,9427,9428,9434,9448,
    9451,10802,10804,10851,10852,10853,10854,10855,10856,10857,11003,11004,
    11005,11006,11022,11023,11024,11025,11104,11105,11106,11107,11108,11122,
    11123,11141,11142,11145,11149,11150,11151,11152,11154,11157,11158,11190,
    11199,11200,11222,11223,11224,11225,11228,11231,11232,11237,11241,11242,
    11244,11245,11254,11255,11258,11259,11274,11275,11276,11277,11349,11350,
    11351,11416,11417,11418,11419,11437,11438,11448,11503,11504,11505,11506,
    11520,11521,11522,11523,11525,11526,11563,11587,11603,11604,11613,11614,
    11616,11617,11618,11620,11621,11658,11697,11698,11700,11701,11737,11748,
    11763,11766,11767,11786,11787,11788,11789,11793,11794,11802,11827,11847,
    11848,11849,11852,11874,11879,11880,11881,11898,11899,11922,11925,11927,
    11928,11963,11964,11984,11985,11986,11991,13166,15030,15056,15058,15069,
    15098,15109,15113,15189,15190,15193,15194,15195,15198,15199,15206,15208,
    15213,15215,15224,15232,15252,17144,17145,17146,17147,17148,17149,17150,
    17151,17152,17153,17156,17157,17158,17159,17160,17161,17162,17163,17164,
    17165,17166,17167,17168,17169,17170,17171,17172,17173,17174,17175,17176,
    17177,17178,17179,17180,17181,17182,17183,17184,17267,17268,17269,17280,
    17281,17282,17283,17284,17285,17286,17287,17288,17289,17290,17291,17292,
    17293,17294,17295,17296,17297,17298,17299,17300,17301,17302,17303,17304,
    17305,17306,17307,17308,17309,17310,17311,17312,17313,17314,17315,17316,
    17317,17318,17319,17320,17321,17322,17323,17324,17325,17326,17327,17328,
    17329,17330,17331,17332,17333,17334,17335,17336,17337,17338,17339,17340,
    17341,17342,17343,17344,17345,17346,17347,17348,42141,42149,42258,43142,
    43143,43287)
            and b.long_desc not like '%powder%'
            and b.long_desc not like '%powdered%'
            and b.long_desc not like '%flour,%'
            and b.long_desc not like '%mix%'
            and b.long_desc not like '%Mix%'
            and upper(b.long_desc) not like '%ENSURE,%'
            and upper(b.long_desc) not like '%ENSURE %'
            and b.long_desc not like '%USDA Commodity%'
            and b.long_desc not like '% flower%'
            and b.long_desc not like 'Game meat%'
            and b.long_desc not like 'Bison%'
            and b.long_desc not like '%caribou%'
            and b.long_desc not like '%Formulated bar%'
            and b.long_desc not like '%formulated bar%'
            and b.long_desc not like '%Alaska Native%'
            and b.long_desc not like 'Elk%'
            and upper(b.long_desc) not like 'COFFEE%'
            and b.long_desc not like 'Seaweed%'
            and b.long_desc not like '%Alaska Native%'
            and b.long_desc not like '%, dry'
            and b.long_desc not like '%, dry,$'
            and b.long_desc not like '%, dried'
            and b.long_desc not like '%, dried,%'
            and b.long_desc not like '%, dehydrated%'
            and b.long_desc not like '%, freeze-dried'
            and b.long_desc not like '%, freeze-dried,%'
            and b.long_desc not like 'Formulated bar,%'
            and b.long_desc not like 'Candies, %'
            and b.long_desc not like 'Water, bottled%'
            and b.long_desc not like 'Beverages,%'
            and b.long_desc not like 'Energy drink,%'
            and not ( food_group_id in (100,500,700,1000,1300,1500,1600) and                 -- disallow raw foods from certain food groups (eg, meat)
    ( long_desc like  '%, raw,%' or long_desc like  '%, raw' or long_desc like  '%, uncooked,%' or long_desc like  '%, uncooked' )  )
    """
        
    conn = sqlite3.connect('data/usda.sql3')
    tmp=pandas.read_sql(nutrient_sql,conn)
    nutrients=tmp.pivot(index='food_id', columns='nutrient_id', values='amount')
    nutrients=nutrients.fillna(0).astype('float32')
    
    #we need to make the requirements and demands conform to the nutrients table above, though they are unaligned.
    
    #TODO: remove dupe records from input file -- this assumes no dupes!
    
    tmp=pandas.read_csv('data/human_requirements.csv')
    y=nutrients.iloc[0,:] # start with the first row of the nutrients table
    y=y.fillna(0) # makes sure all values are filled: NaN->0
    y.columns=nutrients.columns # steal the column indices
    y.name='requirments'
    y[:] = 0 # set whole vector to zero
    y.loc[tmp.iloc[:,0]] = tmp.iloc[:,2].values # fill y with values read from csv ( why .values? see https://stackoverflow.com/questions/24419769/pandas-copying-using-iloc-not-working-as-expected )
    reqd=y.astype('float32')
    
    tmp=pandas.read_csv('data/human_limits.csv')
    y=nutrients.iloc[0,:] # start with the first row of the nutrients table
    y=y.fillna(1e10) # makes sure all values are filled: NaN->1e10
    y.columns=nutrients.columns # steal the column indices
    y.name='requirments'
    y[:] = 0 # set whole vector to zero
    y.loc[tmp.iloc[:,0]] = tmp.iloc[:,2].values # fill y with values read from csv ( why .values? see https://stackoverflow.com/questions/24419769/pandas-copying-using-iloc-not-working-as-expected )
    limt=y.astype('float32')
    limt[limt==0] = 1e10 # if limit is not set, set to very large number
    
    food_desc=pandas.read_sql("select id as food_id, long_desc from food",conn,index_col="food_id")
    
    nutrient_desc=pandas.read_sql("select id,name from nutrient",conn,index_col="id")
    
    return (nutrients,reqd,limt,food_desc,nutrient_desc)

def get_food_lists():
    veg_with_eggs_and_dairy="""
        select distinct id
    from food
    where food_group_id not in (200,500,700,1000,1300,1500,1700,1400,    300,800,1800,2100,2200,3500,3600)
    and id not in (4001,4002,4520,4542,4574,4575,4576,4589,4590,4591,4592,4593,4594,4609,4606,6180,19041)
    and not ( short_desc like '%GELATIN%' )
    and not ( food_group_id=600 and short_desc like '%CHICK%' )
    and not ( food_group_id=600 and short_desc like '%BF %' )
    and not ( food_group_id=600 and short_desc like '%CRAB%' )
    and not ( food_group_id=600 and short_desc like '%BROTH%' )
    and not ( food_group_id=600 and short_desc like '%STOCK%' )
    and not ( food_group_id=600 and short_desc like '%CONSOMME%' )
    and not ( food_group_id=600 and short_desc like '%BOUILLON%' )
    and not ( food_group_id=600 and short_desc like '%FISH%' )
    and not ( food_group_id=600 and short_desc like '%GRAVY%' )
    and not ( food_group_id=600 and short_desc like '%CLAM%' )
    and not ( food_group_id=600 and short_desc like '%HAM%' )
    and not ( food_group_id=600 and short_desc like '%BURGER%' )
    and not ( food_group_id=600 and short_desc like '%BACON%' )
    and not ( food_group_id=600 and short_desc like '%OYSTER%' )
    and not ( food_group_id=600 and short_desc like '%TURKEY%' )
    and not ( food_group_id=600 and short_desc like '%SHRIMP%' )
    """
    conn = sqlite3.connect('data/usda.sql3')
    tmp=pandas.read_sql(veg_with_eggs_and_dairy,conn)
    
    get_food_lists={'veg_with_eggs_and_dairy': tmp.iloc[:,0].to_list() }
    
    return(get_food_lists) 

def do_clust(N,lim,req,nut):
    relevant=pandas.concat( [lim[lim<1.0e10], req[req>0]],axis=1).index # just the nutrients involved in limits; 10e10 and 0 are defaults for limt & reqd
    km=KMeans(n_clusters=N,random_state=10, init='k-means++') 
    clust=km.fit_predict(normalize(nut.loc[:,relevant])) # only cluster using relevant nutrients
    #prop=numpy.bincount(clust).astype('float32') / len(clust) ; unused    
    return clust

# This is how deap wants its evaluate function:
#  it accepts one individual (one basket of foods)
#  and returns a tuple of fitness
def evaluate(individual, nut,limt,reqd,metric_nutrients=[208],metric_weights=[1]):
    nt=nut.iloc[individual,:]
    c = matrix(numpy.repeat(1.0,nt.shape[0]))
    np_G= numpy.concatenate(
                            (   nt.transpose().values, 
                                nt.transpose().multiply(-1.0).values,
                                numpy.diag(numpy.repeat(-1,nt.shape[0])) 
                            )
                           ).astype(numpy.double) 
    G = matrix( np_G ) 
    h = matrix( numpy.concatenate( (
                    limt.values, 
                    reqd.multiply(-1.0).values, 
                    numpy.repeat(0.0,nt.shape[0])
                ) ).astype(numpy.double) )
    try:
        o = solvers.lp(c, G, h, solver='glpk')
    except:
        o={}
        o['status'] = 'nope'
    if o['status'] != 'optimal':
        fit=9e9
    else:
        fit = numpy.dot( numpy.array(o['x']).transpose(), nt.loc[:,metric_nutrients].values * numpy.array(metric_weights) ).item(0)     #numpy.dot(nt.loc[:,metric_nutrients].values,numpy.array(o['x'])).item(0)
    return (fit,)    

def makeclusters(nclust,limt,reqd,nutrients ):
    clust=do_clust(nclust,limt,reqd,nutrients)
    print( '[*] Generated %d food clusters' % nclust )
    return clust

def InitPopulation( pcls, ind_init,nfood, nclust, nseed,clust):
    
    N=numpy.random.multinomial(nfood,pvals=[1.0/nclust]*nclust,size=nseed) # Even probability
    tmp2=[]
    for j in range(N.shape[0]):
        tmp=[]
        for k in numpy.where(N[j,:]>0)[0]:
            t=numpy.random.choice(numpy.where(clust==k)[0],N[j,k])
            tmp=numpy.append(tmp, t).astype(int).tolist()
        tmp2.append(tmp)
        
    return pcls(ind_init(c) for c in tmp2)

def generate_ssdum(random, args):
    nfood=args.get('nfood')
    return rand.choices(range( nutrients.shape[0] ), k=nfood)
