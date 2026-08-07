function y = nanmean(x, dim)
% Compatibility shim for gramm on newer MATLAB versions
if nargin < 2 || isempty(dim)
    y = mean(x, 'omitnan');
else
    y = mean(x, dim, 'omitnan');
end
end