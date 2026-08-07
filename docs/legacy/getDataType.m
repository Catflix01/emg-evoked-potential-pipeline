function data_type = getDataType()
    % GETDATATYPE - Prompts the user to enter the data type ('prestim' or 'response')
    % Output: 
    %   data_type - A string ('prestim' or 'response') based on user input.
    %                     Returns an empty string if the input is invalid or canceled.

    % Define the prompt, title, and input field dimensions
    prompt = {'Do you want to analyze pre-stim or response data? (Enter "prestim" or "response"):'};
    dlgtitle = 'Data Type Input';
    dims = [1 50];  % [height, width] of input field
    definput = {'response'};  % Optional default value

    % Display the input dialog and get user input
    user_input = inputdlg(prompt, dlgtitle, dims, definput);

    % Check if user cancels the dialog
    if isempty(user_input)
        disp('User cancelled input.');
        data_type = '';  % Return empty string if canceled
        return;
    end

    % Extract and validate the input
    data_type = lower(user_input{1});  % Ensure lowercase for consistency
    if ~ismember(data_type, {'prestim', 'response'})
        warning('Invalid input. Please enter either "prestim" or "response".');
        data_type = '';  % Return empty string if input is invalid
    end

    % Display the valid input
    if ~isempty(data_type)
        fprintf('Data Type: %s\n', data_type);
    end
end