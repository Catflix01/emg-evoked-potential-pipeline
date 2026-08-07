function s = nanstd(x, flag, dim)
% Compatibility shim for gramm on newer MATLAB versions
% flag: 0 (normalize by N-1) default, 1 (normalize by N)
if nargin < 2 || isempty(flag), flag = 0; end
if nargin < 3 || isempty(dim)
    s = std(x, flag, 'omitnan');
else
    s = std(x, flag, dim, 'omitnan');
end
end
