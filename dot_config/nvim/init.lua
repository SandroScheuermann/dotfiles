local function transparent_background()
  local groups = {
    "Normal",
    "NormalNC",
    "NormalFloat",
    "FloatBorder",
    "SignColumn",
    "EndOfBuffer",
    "LineNr",
    "CursorLine",
    "CursorLineNr",
    "StatusLine",
    "StatusLineNC",
    "TabLine",
    "TabLineFill",
  }

  for _, group in ipairs(groups) do
    vim.api.nvim_set_hl(0, group, { bg = "NONE" })
  end
end

transparent_background()

vim.api.nvim_create_autocmd("ColorScheme", {
  callback = transparent_background,
})
