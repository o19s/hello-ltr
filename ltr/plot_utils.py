def plot_grades(dat):
    import plotnine as p9

    p = {
        p9.ggplot(dat, p9.aes('grade')) +
        p9.geom_bar() +
        p9.facet_wrap('keywords')
    }

    return p

def plot_features(dat):
    import plotnine as p9
    
    p = {
    p9.ggplot(dat, p9.aes('grade', 'features', color = 'keywords')) +
    p9.geom_jitter(alpha = .5) +
    p9.facet_wrap('feature_id', scales = 'free_y')
    }
    
    return p