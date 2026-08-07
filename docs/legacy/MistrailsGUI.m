function MistrailsGUI
% MistrailsGUI - Flexible MATLAB UIFigure app for structured data entry
% Writes to ./Mistrails.csv and remembers last inputs between sessions
% Written by Mingxiao Liu, LMM :)
% 10/14/2025

%
% Column mapping:
% A: Project            
% B: Subject
% C: Visit              
% D: TimePoint
% E: Side               
% F: Muscle
% G: Protocol
% H: Detail1 (optional) 
% I: Detail2 (optional)
% J: Pulse number (optional)

    appName = 'MistrailsGUI';
    % Set the csvName to the specified full file path
    %    csvName = fullfile(pwd, 'Mistrails.csv');
    csvName = fullfile('S:\SCI Research\NeuroRehab Studies\Active Studies\PHARMA - 1685818\DATA_FOR_PROCESSING\7.CLEAN-DATA', 'Mistrails.csv');
    header = {'Project','Subject','Visit','TimePoint','Side','Muscle','Protocol','Detail1','Detail2','Pulse'};

    % --- UI ---
    f = uifigure('Name','Mistrails Data Entry','Position',[100 100 500 500]);
    g = uigridlayout(f, [9 2], 'RowHeight', {'fit', 'fit', 'fit', 'fit', 'fit', 'fit', 'fit', 50, 'fit'});
    g.ColumnWidth = {'fit', 180};

    % Labels & fields (Placeholders are added back for visual guidance)
    uilabel(g,'Text','1) Project+Subject (e.g., P1Sxx)');
    edProjSub = uieditfield(g,'text');

    uilabel(g,'Text','2) Visit+Time (e.g., V1T0)');
    edVisitTime = uieditfield(g,'text');

    uilabel(g,'Text','3) Side+Muscle (e.g., RAPB)');
    edSideMuscle = uieditfield(g,'text');

    uilabel(g,'Text','4) Protocol (e.g., TMS_120/SCAP)');
    edProtocol = uieditfield(g,'text');

    uilabel(g,'Text','5) Detail1 (optional; e.g., IMM_#/PST)');
    edDetail1 = uieditfield(g,'text');

    uilabel(g,'Text','6) Detail2 (optional; e.g., 30PT/15PT)');
    edDetail2 = uieditfield(g,'text');

    uilabel(g,'Text','7) Pulse # (optional numeric)');
    edPulse = uieditfield(g,'numeric','AllowEmpty','on');

    % Buttons
    btnAdd    = uibutton(g,'Text','ADD','ButtonPushedFcn',@onAdd);
    btnClear  = uibutton(g,'Text','CLEAR','ButtonPushedFcn',@onClear);
    btnFinish = uibutton(g,'Text','FINISH','ButtonPushedFcn',@onFinish);
    btnOpenCsv  = uibutton(g,'Text','OPEN CSV','ButtonPushedFcn',@onOpenCsv);

    % Assign button layout properties for spanning
    btnAdd.Layout.Row = 8; btnAdd.Layout.Column = 1;
    btnClear.Layout.Row = 8; btnClear.Layout.Column = 2;
    btnOpenCsv.Layout.Row = 9; btnOpenCsv.Layout.Column = [1 2];
    btnFinish.Layout.Row = 10; btnFinish.Layout.Column = [1 2];
   

    % Preload previous defaults (first run => all empty)
    defaults = getDefaults();
    if ~isempty(defaults)
        setField(edProjSub, defaults, 'ProjSub');
        setField(edVisitTime, defaults, 'VisitTime');
        setField(edSideMuscle, defaults, 'SideMuscle');
        setField(edProtocol, defaults, 'Protocol');
        setField(edDetail1, defaults, 'Detail1');
        setField(edDetail2, defaults, 'Detail2');
        if isfield(defaults,'Pulse') && ~isempty(defaults.Pulse)
            edPulse.Value = defaults.Pulse;
        end
    end

    % Ensure CSV exists (write header if new)
    ensureCsvExists(csvName, header);

    % --- Callbacks ---

    function onAdd(~,~)
        % Read fields
        s1 = strtrim(edProjSub.Value);
        s2 = strtrim(edVisitTime.Value);
        s3 = strtrim(edSideMuscle.Value);
        s4 = strtrim(edProtocol.Value);
        s5 = strtrim(edDetail1.Value);  % optional
        s6 = strtrim(edDetail2.Value);  % optional
        p  = edPulse.Value;             % numeric (optional)

        % --- VALIDATION CHECK: Do not add if mandatory fields are empty ---
        if isempty(s1) || isempty(s2) || isempty(s3) || isempty(s4)
            uialert(f,'Please fill in all mandatory fields (1-4).','Incomplete Entry','Icon','error');
            return; % Exit the callback if validation fails
        end

         % --- VALIDATION CHECK 2: If Protocol is 'SCAP', Detail1 and Detail2 cannot be empty ---
        if strcmpi(s4, 'SCAP')
            if isempty(s5) || isempty(s6)
                uialert(f,'When Protocol is SCAP, Detail1 and Detail2 cannot be empty.','Validation Error','Icon','error');
                return; % Exit the callback if validation fails
            end
        end

        % Parse (best-effort, no hard validations)
        [proj, subj]   = parseProjSub(s1);       % A,B
        [visit, tpt]   = parseVisitTime(s2);     % C,D
        [side, musc]   = parseSideMuscle(s3);    % E,F
        exper          = parseFreeText(s4);      % G
        detail1        = parseFreeText(s5);      % H
        detail2        = parseFreeText(s6);      % I
        pulse          = parsePulseFlexible(p);  % J ('' if empty)

          % Create a table row from the current input for comparison
        newRowTable = cell2table({proj, subj, visit, tpt, side, musc}, ...
            'VariableNames', {'Project','Subject','Visit','TimePoint','Side','Muscle'});

        % --- DUPLICATE CHECK: Read existing CSV data and check for matches ---
        try
            existingData = readtable(csvName, 'TextType', 'string'); % Read as string type
            
            % Check if there are any non-timestamp rows to compare
            if size(existingData, 1) > 0
                % The last two rows are timestamps, so exclude them from the comparison
                if size(existingData, 1) > 1 && startsWith(string(existingData{end-1, 1}), 'Run completed at')
                    existingData = existingData(1:end-2,:);
                end
                
                % Compare mandatory fields (first 6 columns)
                existingKeys = existingData(:, 1:6);
                isDuplicate = ismember(newRowTable, existingKeys, 'rows');
                if isDuplicate
                    uialert(f,'This entry already exists. No new row was added.','Duplicate Entry','Icon','warning');
                    return; % Exit the callback if a duplicate is found
                end
            end
        catch
            % This handles the first run where the CSV file might not exist yet.
            % No action is needed here, as it will be created below.
        end

        % Append row to CSV
        row = {proj, subj, visit, tpt, side, musc, exper, detail1, detail2, pulse};
        appendCsvRow(csvName, row);

        % Save current values as next-run defaults
        newDefaults.ProjSub    = s1;
        newDefaults.VisitTime  = s2;
        newDefaults.SideMuscle = s3;
        newDefaults.Protocol   = s4;
        newDefaults.Detail1    = s5;
        newDefaults.Detail2    = s6;
        newDefaults.Pulse      = pulse;
        setpref(appName,'defaults', newDefaults);

        uialert(f,'Row added to Mistrails.csv','Success','Icon','success');
    end

    function onClear(~,~)
        edProjSub.Value    = '';
        edVisitTime.Value  = '';
        edSideMuscle.Value = '';
        edProtocol.Value   = '';
        edDetail1.Value    = '';
        edDetail2.Value    = '';
        edPulse.Value      = [];
    end

    function onFinish(~,~)
        % Call onAdd to perform validation and add the final entry
        onAdd();
        
        % Check if the last add was successful before proceeding
        % This is a simple check, a more robust check would use a return value
        if isempty(edProjSub.Value) || isempty(edVisitTime.Value) || isempty(edSideMuscle.Value) || isempty(edProtocol.Value)
            % If the fields are still empty after the onAdd call, it means validation failed.
            return;
        end

        % Write timestamp row in first column, then a blank row
        tstamp = datestr(now,'yyyy-mm-dd HH:MM:SS');
        appendCsvRow(csvName, {['Run completed at ' tstamp], '', '', '', '', '', '', '', '', ''});
        appendCsvRow(csvName, {'','','','','','','','','',''});

        uialert(f,'Saved timestamp and closed the session.','Done','Icon','success');
        pause(0.2);
        close(f);
    end

    function onOpenCsv(~,~)
        try
            open(csvName);
        catch ME
            uialert(f, ['Could not open CSV file: ' ME.message], 'Error Opening File', 'Icon', 'error');
        end
    end

    % --- Helpers: persistence & CSV ---

    function d = getDefaults()
        if ispref(appName,'defaults')
            d = getpref(appName,'defaults');
        else
            d = struct();
        end
    end

    function setField(ed, d, name)
        if isfield(d,name) && ~isempty(d.(name))
            ed.Value = d.(name);
        end
    end

    function ensureCsvExists(fn, hdr)
        % Add error handling for folder creation
        [filepath, ~, ~] = fileparts(fn);
        if ~isfolder(filepath)
            mkdir(filepath);
        end
        if ~isfile(fn)
            fid = fopen(fn,'w');
            assert(fid>0, 'Cannot create %s', fn);
            fprintf(fid,'%s\n', strjoin(hdr, ','));
            fclose(fid);
        end
    end

    function appendCsvRow(fn, cells)
        % Escape any commas by quoting the field if needed
        out = cellfun(@(c) fieldToCsv(c), cells, 'UniformOutput', false);
        line = strjoin(out, ',');
        fid = fopen(fn,'a');
        assert(fid>0, 'Cannot open %s for append', fn);
        fprintf(fid,'%s\n', line);
        fclose(fid);
    end

    function s = fieldToCsv(v)
        if isnumeric(v)
            if isempty(v) || ~isfinite(v)
                s = '';
            else
                s = num2str(v);
            end
        else
            s = char(v);
        end
        % Quote if contains comma, quote, or leading/trailing space
        needsQuote = contains(s, {',','"'} ) || ~strcmp(strtrim(s), s);
        if contains(s, '"')
            s = strrep(s, '"', '""'); % CSV escape double quotes
        end
        if needsQuote
            s = ['"' s '"'];
        end
    end

    % --- Flexible Parsers (no hard validation) ---

    function [proj, subj] = parseProjSub(s)
        % Best-effort split: first 3 alnum chars as "project", remaining digits as "subject".
        % If it doesn't match, put whole string in project and leave subject blank.
        t = upper(strtrim(s));
        m = regexp(t, '^([A-Z0-9]{3})(\d+)$', 'tokens', 'once');
        if ~isempty(m)
            proj = m{1};
            subj = m{2};
        else
            proj = t;
            subj = '';
        end
    end

    function [visit, tpt] = parseVisitTime(s)
        % Prefer VxTx; otherwise if there's a 'T', split at the first 'T'.
        % Else put all into visit and leave time blank.
        t = upper(strtrim(s));
        m = regexp(t, '^V(\d+)T(\d+)$', 'tokens', 'once');
        if ~isempty(m)
            visit = ['V' m{1}];
            tpt   = ['T' m{2}];
            return;
        end
        tidx = find(t == 'T', 1, 'first');
        if ~isempty(tidx)
            left  = strtrim(t(1:tidx-1));
            right = strtrim(t(tidx+1:end));
            if ~isempty(left), visit = left; else, visit = ''; end
            if ~isempty(right), tpt = right; else, tpt = ''; end
        else
            visit = t;
            tpt   = '';
        end
    end

    function [side, musc] = parseSideMuscle(s)
        % Expects RAPB, RFDI, or similar. Split at first non-letter.
        t = upper(strtrim(s));
        m = regexp(t, '^([A-Z]+)(\w*)$', 'tokens', 'once');
        if ~isempty(m)
            side = m{1};
            musc = m{2};
        else
            side = '';
            musc = t;
        end
    end

    function exper = parseFreeText(s)
        exper = strtrim(s);
    end

    function pulse = parsePulseFlexible(p)
        if isempty(p) || p < 1 || ~isfinite(p)
            pulse = ''; % Treat invalid or empty pulse as empty string
        else
            pulse = p;
        end
    end
end
