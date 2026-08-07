%% Section 2: CODE CROSS CHECK
% ------------------------------------------------------
% Verifies that ALL-DATA channels match the mapping in
% Centralized-NIDAQ-System.xlsx (any sheet; prefers "Library").
% For each CSV under *_TMS / *_TSS it:
%  - parses filename: subject/visit/time/target/trigger/date
%  - finds the row for that date in the library
%  - builds a name->columnIndex map for that date's channel lineup
%  - checks that target & trigger column indices are within CSV width

disp('--- Section 2: CODE CROSS CHECK ---');

% ---- Preconditions from Section 1 ----
if ~exist('mainFolder','var') || ~exist('dataMain','var')
    error('Please run Section 1 first to define mainFolder and dataMain.');
end
allDataDir = fullfile(dataMain, 'ALL-DATA');
if ~isfolder(allDataDir)
    error('ALL-DATA folder not found at: %s', allDataDir);
end

% --- Create log file ---
timestamp = datestr(now, 'mmddyyyy');
logFile = fullfile(dataMain, sprintf('Code Cross Check_%s.txt', timestamp));
fid = fopen(logFile, 'w');
if fid == -1
    error('Could not open log file for writing: %s', logFile);
end

fprintf(fid, '--- Section 2: CODE CROSS CHECK ---\n');
fprintf(fid, 'Run time: %s\n\n', datestr(now));

% ---- Locate the libraChanNamesByRowry workbook next to this script ----
thisScriptDir = fileparts(mfilename('fullpath'));
libraryFile   = fullfile(thisScriptDir, 'Centralized-NIDAQ-System.xlsx');
if ~isfile(libraryFile)
    error('Centralized-NIDAQ-System.xlsx not found at: %s', libraryFile);
end

% =================== Robust Library Loader (readcell-based) ====================
% Produces:
%   LibDate         : Nx1 datetime (valid rows only)
%   ChanNamesByRow  : NxM string matrix (uppercased, trimmed; M>=1)
%   LibKey          : Nx1 string, 'ddMMyyyy'
%   getMapForKey()  : @(key) -> containers.Map(name -> 1-based channel index)

try
    shNames = sheetnames(libraryFile);
catch
    [~, shNames] = xlsfinfo(libraryFile); % fallback
end
if isempty(shNames)
    error('No sheets found in %s', libraryFile);
end

fprintf('Sheets found: %s\n', strjoin(cellstr(string(shNames)), ' | '));

% --- Helper: read a sheet with readcell, auto-detect date col, build matrices
function [LibDate, ChanNamesByRow] = readLibrarySheetRaw_cells(file, sheet)
    % Read raw cells so we see the sheet exactly as-is
    C = readcell(file, 'Sheet', sheet);

    fprintf('Reading sheet "%s": size %dx%d\n', sheet, size(C,1), size(C,2));

    % Quick exit if sheet is empty
    if isempty(C)
        LibDate = NaT(0,1); ChanNamesByRow = strings(0,0); return;
    end

    % Trim trailing empty rows/cols (conservative)
    % Define "empty-ish" predicate for a single cell value
    isEmptyVal = @(v) ( isempty(v) || ...
                        (isstring(v) && all(strlength(v)==0)) || ...
                        (ischar(v)   && all(isspace(v))) );

    % Drop trailing completely-empty rows
    keepRow = true(size(C,1),1);
    for r = 1:size(C,1)
        rowVals = C(r,:);
        if all(cellfun(isEmptyVal,rowVals))
            keepRow(r) = false;
        end
    end
    if any(keepRow)
        last = find(keepRow,1,'last');
        C = C(1:last,:);
    end

    % Drop trailing completely-empty columns
    keepCol = true(1,size(C,2));
    for c = 1:size(C,2)
        colVals = C(:,c);
        if all(cellfun(isEmptyVal,colVals))
            keepCol(c) = false;
        end
    end
    if any(keepCol)
        last = find(keepCol,1,'last');
        C = C(:,1:last);
    end

    [R,Cn] = size(C);

    % ---- Find the Date column & header row ----
    dateCol = 1;   % default to first column
    hdrRow  = 0;   % 0 means "no explicit header row found"

    maxScanRows = min(5,R);  % only scan first few rows for a 'Date' header
    found = false;
    for r = 1:maxScanRows
        for c = 1:Cn
            v = C{r,c};
            if ischar(v) || isstring(v)
                if strcmpi(strtrim(string(v)),'Date')
                    dateCol = c;
                    hdrRow  = r;
                    found = true;
                    break;
                end
            end
        end
        if found, break; end
    end

    % ---- Build the date vector from rows below header (or from row 1 if no header) ----
    startRow = hdrRow + 1;
    if startRow > R
        LibDate = NaT(0,1); ChanNamesByRow = strings(0,0); return;
    end
    dateCells = C(startRow:R, dateCol);

    % Parse dates robustly
    LibDate = NaT(numel(dateCells),1);
    % Numeric excel serials
    isNum = cellfun(@(x) isnumeric(x) && isfinite(x), dateCells);
    if any(isNum)
        try
            LibDate(isNum) = datetime([dateCells{isNum}]','ConvertFrom','excel');
        catch
        end
    end

    % datetime objects
    isDT = cellfun(@(x) isdatetime(x), dateCells);
    if any(isDT)
        LibDate(isDT) = [dateCells{isDT}]';
    end
    
    % Text dates
    isTxt = cellfun(@(x) ischar(x) || isstring(x), dateCells);
    if any(isTxt)
        txt = strtrim(string(dateCells(isTxt)));
        dtTxt = NaT(sum(isTxt),1);
        fmts = ["M/d/yyyy","MM/dd/yyyy","d/M/yyyy","dd/MM/yyyy", ...
                "yyyy-MM-dd","dd-MMM-yyyy","M/d/yy","MM/dd/yy"];
        for kfmt = 1:numel(fmts)
            m = isnat(dtTxt);
            try
                dtTxt(m) = datetime(txt(m),'InputFormat',fmts(kfmt),'Locale','en_US');
            catch
            end
        end
        m = isnat(dtTxt) & txt~="";
        if any(m)
            try
                dtTxt(m) = datetime(txt(m)); % final guess
            catch
            end
        end
        LibDate(isTxt) = dtTxt;
    end

    % Keep only valid dates
    keep = ~isnat(LibDate);
    LibDate = LibDate(keep);
    if isempty(LibDate)
        ChanNamesByRow = strings(0,0); return;
    end

    % ---- Channel columns = all columns to the RIGHT of the date column ----
    chanCols = (dateCol+1):Cn;

    % QUICK FIX: the first col after Date is an ID/Participant column -> drop it
    if ~isempty(chanCols)
        chanCols = chanCols(2:end);
    end

    if isempty(chanCols)
        ChanNamesByRow = strings(0,0); return;
    end

    ChanCells = C(startRow:R, chanCols);
    ChanCells = ChanCells(keep, :);  % align to kept date rows


    % Drop channel columns that are entirely empty across kept rows
    if ~isempty(ChanCells)
        keepChanCol = true(1,size(ChanCells,2));
        for j = 1:size(ChanCells,2)
            colj = ChanCells(:,j);
            if all(cellfun(isEmptyVal,colj))
                keepChanCol(j) = false;
            end
        end
        ChanCells = ChanCells(:, keepChanCol);
    end

    % Normalize to uppercase trimmed strings (no ismissing calls)
    if isempty(ChanCells)
        ChanNamesByRow = strings(numel(LibDate), 0);
    else
        S = strings(size(ChanCells));
        for rr = 1:size(ChanCells,1)
            for cc = 1:size(ChanCells,2)
                val = ChanCells{rr,cc};
                if isempty(val)
                    S(rr,cc) = "";
                elseif isstring(val) || ischar(val)
                    S(rr,cc) = upper(strtrim(string(val)));
                elseif isnumeric(val)
                    S(rr,cc) = upper(strtrim(string(val)));
                else
                    S(rr,cc) = upper(strtrim(string(string(val))));
                end
            end
        end
        ChanNamesByRow = S;
    end
end

% Try 'Library' first; fall back to the best sheet by valid-date count
prefIdx = find(strcmpi(shNames, 'Library'), 1);
LibDate = NaT(0,1); ChanNamesByRow = strings(0,0);

if ~isempty(prefIdx)
    [LibDate, ChanNamesByRow] = readLibrarySheetRaw_cells(libraryFile, shNames{prefIdx});
end

if isempty(LibDate) || numel(LibDate)==0
    bestN = -inf; tmpDate = NaT(0,1); tmpChan = strings(0,0); bestSheet = '';
    for iSh = 1:numel(shNames)
        [dtTest, chTest] = readLibrarySheetRaw_cells(libraryFile, shNames{iSh});
        if numel(dtTest) > bestN
            bestN = numel(dtTest); tmpDate = dtTest; tmpChan = chTest; bestSheet = shNames{iSh};
        end
    end
    LibDate = tmpDate; ChanNamesByRow = tmpChan;
    if bestN <= 0
        error('Could not find a usable date column on any sheet of %s', libraryFile);
    else
        fprintf('Using sheet "%s" (valid date rows: %d)\n', bestSheet, bestN);
    end
else
    fprintf('Using sheet "Library" (valid date rows: %d)\n', numel(LibDate));
end

% Sanity: sizes match?
if size(ChanNamesByRow,1) ~= numel(LibDate)
    error('Library alignment issue: LibDate rows = %d, ChanNamesByRow rows = %d', ...
        numel(LibDate), size(ChanNamesByRow,1));
end

% Normalize day resolution and build keys
LibDate = dateshift(LibDate, 'start', 'day');

% (Optional) If you want to drop truly ancient serials, uncomment:
% cutoff = datetime(2010,1,1);
% keep = LibDate >= cutoff;
% LibDate = LibDate(keep);
% ChanNamesByRow = ChanNamesByRow(keep, :);

LibKey = string(datestr(LibDate, 'ddmmyyyy'));   % e.g., "28082025"

% After LibKey is built:
testRow = find(LibKey == "17032022", 1);  % pick a known date key
if ~isempty(testRow)
    disp(ChanNamesByRow(testRow, 1:10));  % peek first 10 channel names
end

% Quick diagnostics
fprintf('Library finalized: %d rows x %d channel-cols\n', numel(LibKey), size(ChanNamesByRow,2));
if ~isempty(LibKey)
    fprintf('First 5 date keys: %s\n', strjoin(cellstr(LibKey(1:min(5,end))), ', '));
end

% Accessor map builder
getMapForKey = @(key) buildChannelMapForKey(key, LibKey, ChanNamesByRow);

% ===================== Walk ALL-DATA and validate CSVs =====================
subs = dir(fullfile(allDataDir, 'P1S*'));  % P1SXX
subs = subs([subs.isdir]);

if isempty(subs)
    fprintf('No P1SXX subject folders found under %s\n', allDataDir);
end

totalFiles = 0; totalPass = 0; totalFail = 0;

for iSub = 1:numel(subs)
    subPath = fullfile(subs(iSub).folder, subs(iSub).name);

    % Level 2: P1SXX_VXEX_DDMMYYYY
    lvl2 = dir(fullfile(subPath, [subs(iSub).name '_V*E*_*']));
    lvl2 = lvl2([lvl2.isdir]);

    for iL2 = 1:numel(lvl2)
        l2Path = fullfile(lvl2(iL2).folder, lvl2(iL2).name);

        % Level 3: *_TMS and *_TSS subfolders
        runDirs = [dir(fullfile(l2Path, '*_TMS')); dir(fullfile(l2Path, '*_TSS'))];

        for iRun = 1:numel(runDirs)
            runPath = fullfile(runDirs(iRun).folder, runDirs(iRun).name);

            csvs = dir(fullfile(runPath, '*.csv'));
            for iF = 1:numel(csvs)
                fpath = fullfile(csvs(iF).folder, csvs(iF).name);
                totalFiles = totalFiles + 1;

                info = parseRunFilename(csvs(iF).name);  % filename parser below

                % Basic presence check
                if isempty(info.TARG) || isempty(info.TRIG) || strlength(info.DateRaw8)==0
                    fprintf(2,'[FAIL] %s | Missing piece(s): TARG="%s" TRIG="%s" DateRaw8="%s"\n', ...
                        csvs(iF).name, string(info.TARG), string(info.TRIG), string(info.DateRaw8));
                    fprintf(fid,'[FAIL] %s | Missing piece(s): TARG="%s" TRIG="%s" DateRaw8="%s"\n', ...
                        csvs(iF).name, string(info.TARG), string(info.TRIG), string(info.DateRaw8));
                    totalFail = totalFail + 1;
                    continue;
                end

                % Try DDMMYYYY first, then MMDDYYYY, using whichever exists in the library
                key_dmy = to_ddmmyyyy_from_raw8(info.DateRaw8, 'DMY');
                key_mdy = to_ddmmyyyy_from_raw8(info.DateRaw8, 'MDY');

                chanMap = [];
                chosenKey = "";

                if strlength(key_dmy)>0
                    chanMap = getMapForKey(key_dmy);
                    if ~isempty(chanMap)
                        chosenKey = key_dmy;
                    end
                end
                if isempty(chanMap) && strlength(key_mdy)>0
                    chanMap = getMapForKey(key_mdy);
                    if ~isempty(chanMap)
                        chosenKey = key_mdy;
                    end
                end

                if isempty(chanMap)
                    fprintf(2,'[FAIL] %s | Date keys not found in Library (tried DMY=%s, MDY=%s)\n', ...
                        csvs(iF).name, key_dmy, key_mdy);
                    fprintf(fid,'[FAIL] %s | Date keys not found in Library (tried DMY=%s, MDY=%s)\n', ...
                        csvs(iF).name, key_dmy, key_mdy);
                    totalFail = totalFail + 1;
                    continue;
                end

                % Use the chosen key going forward
                info.DateKey = chosenKey;

                targName = char(upper(string(info.TARG)));
                trigName = char(upper(string(info.TRIG)));

                targIdx = getOrEmpty(chanMap, targName);
                trigIdx = getOrEmpty(chanMap, trigName);


                if isempty(targIdx) || isempty(trigIdx)
                    parts = {};
                    if isempty(targIdx), parts{end+1} = 'TARG'; end
                    if isempty(trigIdx), parts{end+1} = 'TRIG'; end
                    missingStr = strjoin(parts, ' & ');

                    fprintf(2,'[FAIL] %s | Missing %s in Library (DateKey=%s)\n', ...
                        csvs(iF).name, missingStr, char(info.DateKey));
                    fprintf(fid,'[FAIL] %s | Missing %s in Library (DateKey=%s)\n', ...
                        csvs(iF).name, missingStr, char(info.DateKey));
                    totalFail = totalFail + 1;
                    continue;
                end


                % Load CSV
                try
                    M = readmatrix(fpath);
                catch
                    Ttmp = readtable(fpath, 'FileType','text');
                    M = table2array(Ttmp);
                end
                if isempty(M)
                    fprintf(2,'[FAIL] %s | Empty CSV\n', csvs(iF).name);
                    totalFail = totalFail + 1;
                    fprintf(fid,'[FAIL] %s | Empty CSV\n', csvs(iF).name);
                    continue;
                end

                nCols = size(M,2);
                targInRange = (targIdx >= 1) && (targIdx <= nCols);
                trigInRange = (trigIdx >= 1) && (trigIdx <= nCols);

                if targInRange && trigInRange
                    fprintf('[PASS] %s | DateKey=%s | TARG=%s @ col %d | %s @ col %d | CSV cols=%d\n', ...
                        csvs(iF).name, info.DateKey, targName, targIdx, trigName, trigIdx, nCols);
                    fprintf(fid,'[PASS] %s | DateKey=%s | TARG=%s @ col %d | %s @ col %d | CSV cols=%d\n', ...
                        csvs(iF).name, info.DateKey, targName, targIdx, trigName, trigIdx, nCols);
                    totalPass = totalPass + 1;
                else
                    fprintf(2,'[FAIL] %s | DateKey=%s | Expected %s col=%d, %s col=%d but CSV cols=%d\n', ...
                        csvs(iF).name, info.DateKey, targName, targIdx, trigName, trigIdx, nCols);
                    fprintf(fid,'[FAIL] %s | DateKey=%s | Expected %s col=%d, %s col=%d but CSV cols=%d\n', ...
                        csvs(iF).name, info.DateKey, targName, targIdx, trigName, trigIdx, nCols);
                    totalFail = totalFail + 1;
                end

            end
        end
    end
end

fprintf('\nCODE CROSS CHECK complete: %d files | %d PASS | %d FAIL\n', totalFiles, totalPass, totalFail);
fprintf(fid, '\nCODE CROSS CHECK complete: %d files | %d PASS | %d FAIL\n', totalFiles, totalPass, totalFail);   % write to file
disp('--- End CODE CROSS CHECK ---');
disp(' '); %No P1SXX subject folders

% ======================= Local helpers for this section ====================
function key = to_ddmmyyyy_from_raw8(raw8, prefer)
% Converts a raw 8-digit date string (e.g., '03142024') into ddMMyyyy key.
% Handles both string/char inputs and short/invalid inputs gracefully.

% Ensure input is text
if isempty(raw8)
    key = "";
    return;
end

% Convert string to char if needed
if isstring(raw8)
    raw8 = char(raw8);
end

% Strip whitespace
raw8 = strtrim(raw8);

% Validate length
if numel(raw8) < 8
    key = "";
    return;
end

% Extract parts
d = str2double(raw8(1:2));
m = str2double(raw8(3:4));
y = str2double(raw8(5:8));

isValid = @(dd,mm,yy) (yy>=1900 && yy<=2100 && mm>=1 && mm<=12 && dd>=1 && dd<=31);

dmy_ok = isValid(d,m,y);   % assume DD/MM/YYYY
mdy_ok = isValid(m,d,y);   % assume MM/DD/YYYY

if dmy_ok && ~mdy_ok
    dd = d; mm = m;
elseif mdy_ok && ~dmy_ok
    dd = m; mm = d;         % convert MMDD -> DDMM
elseif dmy_ok && mdy_ok
    if strcmpi(prefer,'MDY')
        dd = m; mm = d;
    else
        dd = d; mm = m;
    end
else
    key = "";
    return;
end

key = sprintf('%02d%02d%04d', dd, mm, y);  % ddMMyyyy
end

function chanMap = buildChannelMapForKey(key, LibKey, ChanNamesByRow)
    % key is like 'ddmmyyyy'
    ix = find(LibKey == string(key), 1, 'first');
    if isempty(ix)
        chanMap = [];
        return;
    end

    names = ChanNamesByRow(ix, :);  % 1 x M string row (may contain "", <missing>, "NaN", etc.)

    % Use explicit types so MATLAB doesn't guess
    chanMap = containers.Map('KeyType','char','ValueType','double');

    for k = 1:numel(names)
        nm = names(k);                      % string scalar
        % Skip missing/empty/NaN-ish entries
        if ismissing(nm) || strlength(nm)==0
            continue;
        end
        nm = upper(strip(nm));
        if nm == "NAN"
            continue;
        end
        % Convert to char to satisfy containers.Map key type
        nmch = char(nm);

        % Optional: normalize whitespace sequences
        % nmch = regexprep(nmch, '\s+', ' ');

        if ~isKey(chanMap, nmch)
            chanMap(nmch) = k;              % 1-based channel position
        end
    end
end

function v = getOrEmpty(mp, key)
    % ensure char key
    if isstring(key), key = char(key); end
    if ~ischar(key),  key = char(string(key)); end
    if isKey(mp, key), v = mp(key); else, v = []; end
end


function info = parseRunFilename(fname)
    info = struct('SUB','', 'VIS','', 'TP','', 'TARG','', 'TRIG','', 'INT','', ...
                  'Date', NaT, 'DateKey', "", 'DateRaw8',"");

    [~, base, ~] = fileparts(fname);
    B = upper(base);

    m = regexp(B, '(P1S\d{2})', 'tokens', 'once');
    if ~isempty(m), info.SUB = m{1}; end

    m = regexp(B, '_(V\d)T(\d)_', 'tokens', 'once');
    if ~isempty(m), info.VIS = m{1}; info.TP = m{2}; end

    m = regexp(B, '_(?<TARG>[A-Z]{2,5})_(TMS|TSS)_', 'names', 'once');
    if ~isempty(m), info.TARG = m.TARG; end

    m = regexp(B, '_(TMS|TSS)_', 'tokens', 'once');
    if ~isempty(m), info.TRIG = m{1}; end

    m = regexp(B, '_(TMS|TSS)_(?<INT>[^_]+)_', 'names', 'once');
    if ~isempty(m), info.INT = m.INT; end

    % Capture the 8 digits before -HH-mm-ss
    m = regexp(B, '_([0-9]{8})-[0-9]{2}-[0-9]{2}-[0-9]{2}$', 'tokens', 'once');
    if ~isempty(m)
        info.DateRaw8 = string(m{1});           % store raw
        % Optional datetime for display if you want:
        try
            % Try DDMMYYYY first for display only
            info.Date = datetime(m{1},'InputFormat','ddMMyyyy');
        catch
            try
                info.Date = datetime(m{1},'InputFormat','MMddyyyy');
            catch
                info.Date = NaT;
            end
        end
    end
end
