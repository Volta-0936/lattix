H='table e = (0,1,4), (0,2,1), (2,1,2), (1,3,5)\nfield d : min bound 16\nd[0] <- 0\n'
printf "${H}d[j] <- d[i] + w   for (i,j,w) in e\nprint d\n" > a_min.lx
printf "${H}d[j] <- d[i] + w + 1   for (i,j,w) in e\nprint d\n" > b_3term.lx
printf "${H}d[j] <- d[i] + w   for (i,j,w) in e if w >= 2\nprint d\n" > c_ge.lx
printf "${H}d[j] <- d[i] + w   for (i,j,w) in e if w == 4\nprint d\n" > d_eq.lx
printf "${H}d[j] <- d[i] + w   for (i,j,w) in e if w != 4\nprint d\n" > e_ne.lx
printf "${H}d[j] <- d[i] + w   for (i,j,w) in e if w <= 4 if i == 0\nprint d\n" > f_two.lx
printf "${H}d[j] <- d[i] - w   for (i,j,w) in e\nprint d\n" > g_sub.lx
printf "${H}d[j] <- d[i] + w * 2   for (i,j,w) in e\nprint d\n" > h_mul.lx
printf "${H}d[j] <- d[i] + w / 2   for (i,j,w) in e\nprint d\n" > i_div.lx
printf "${H}d[j] <- d[i] + w %% 3   for (i,j,w) in e\nprint d\n" > j_mod.lx
printf 'table e = (0,1,4), (0,2,1), (2,1,2), (1,3,5)\nfield m : max bound 16\nm[0] <- 0\nm[j] <- m[i] + w   for (i,j,w) in e\nprint m\n' > k_max.lx
printf 'table e = (0,1), (1,2), (2,3)\nfield r : or bound 16\nr[0] <- true\nr[j] <- true   for (i,j) in e\nprint r\n' > l_or.lx
printf 'table e = (0,1), (1,2), (2,3)\nfield r : or bound 16\nr[0] <- true\nr[j] <- true   for (i,j) in e if i >= 1\nprint r\n' > m_orguard.lx
