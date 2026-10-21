Attribute VB_Name = "modExportarGestao"
Option Explicit

' =====================================================================
' ENVIAR E-MAIL PARA O SISTEMA GESTAO DE DEMANDAS (Python)
' Outlook classico -> pacote JSON + anexos na pasta de entrada (inbox).
'
' O que faz:
'   - exporta assunto, remetente, data, corpo e anexos do e-mail selecionado
'   - grava um .json em INBOX_PATH (e os anexos numa subpasta)
'   - o sistema Python importa esses pacotes pelo botao "Importar e-mails"
'
' Nao envia, nao responde e nao altera o e-mail.
' =====================================================================

' Pasta de entrada do sistema (deve existir ou sera criada pelo Python).
Private Const INBOX_PATH As String = "C:\Users\ivani\OneDrive\Downloads\Projetos\Gestao_Demandas\dados\inbox"
Private Const TITULO As String = "Gestao de Demandas"
Private Const PR_SMTP As String = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"

Public Sub EnviarParaGestao()
    On Error GoTo ErrHandler

    Dim mail As Outlook.MailItem
    Set mail = SelecionarEmail()
    If mail Is Nothing Then Exit Sub

    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FolderExists(INBOX_PATH) Then
        MsgBox "Pasta de entrada nao encontrada:" & vbCrLf & INBOX_PATH & vbCrLf & vbCrLf & _
               "Ajuste a constante INBOX_PATH no codigo da macro.", vbCritical, TITULO
        Exit Sub
    End If

    Dim idEnvio As String
    idEnvio = Format$(Now, "yyyymmdd_hhnnss")

    Dim pastaAnexos As String
    pastaAnexos = INBOX_PATH & "\" & idEnvio & "_anexos"

    Dim anexosJson As String
    anexosJson = SalvarAnexos(mail, pastaAnexos, fso)

    Dim pastaSalva As String
    If Len(anexosJson) > 0 Then pastaSalva = pastaAnexos Else pastaSalva = ""

    Dim recebido As Date
    recebido = mail.ReceivedTime

    Dim json As String
    json = "{" & vbLf
    json = json & "  ""entry_id"": " & JStr(mail.EntryID) & "," & vbLf
    json = json & "  ""assunto"": " & JStr(SafeText(mail.Subject)) & "," & vbLf
    json = json & "  ""remetente_nome"": " & JStr(SafeText(mail.SenderName)) & "," & vbLf
    json = json & "  ""remetente_email"": " & JStr(EmailRemetente(mail)) & "," & vbLf
    json = json & "  ""recebido"": " & JStr(Format$(recebido, "yyyy-mm-dd") & "T" & Format$(recebido, "hh:nn:ss")) & "," & vbLf
    json = json & "  ""corpo"": " & JStr(SafeText(mail.Body)) & "," & vbLf
    json = json & "  ""pasta_anexos"": " & JStr(pastaSalva) & "," & vbLf
    json = json & "  ""anexos"": [" & anexosJson & "]" & vbLf
    json = json & "}"

    GravarUtf8 INBOX_PATH & "\" & idEnvio & ".json", json

    MsgBox "E-mail enviado para a fila do sistema." & vbCrLf & vbCrLf & _
           "Assunto: " & SafeText(mail.Subject) & vbCrLf & _
           "Anexos: " & mail.Attachments.Count & vbCrLf & vbCrLf & _
           "Abra o sistema e clique em 'Importar e-mails'.", vbInformation, TITULO
    Exit Sub

ErrHandler:
    MsgBox "Erro ao enviar o e-mail:" & vbCrLf & Err.Description, vbCritical, TITULO
End Sub

Private Function SelecionarEmail() As Outlook.MailItem
    Dim exp As Outlook.Explorer
    Set exp = Application.ActiveExplorer

    If exp Is Nothing Then
        MsgBox "Abra uma pasta de e-mails e selecione um e-mail.", vbExclamation, TITULO
        Exit Function
    End If
    If exp.Selection.Count = 0 Then
        MsgBox "Selecione um e-mail.", vbExclamation, TITULO
        Exit Function
    End If
    If TypeName(exp.Selection.Item(1)) <> "MailItem" Then
        MsgBox "O item selecionado nao e um e-mail.", vbExclamation, TITULO
        Exit Function
    End If

    Set SelecionarEmail = exp.Selection.Item(1)
End Function

Private Function SalvarAnexos(mail As Outlook.MailItem, pasta As String, fso As Object) As String
    Dim i As Long
    Dim att As Outlook.Attachment
    Dim nome As String
    Dim caminho As String
    Dim lista As String

    If mail.Attachments.Count = 0 Then Exit Function
    If Not fso.FolderExists(pasta) Then fso.CreateFolder pasta

    For i = 1 To mail.Attachments.Count
        Set att = mail.Attachments.Item(i)
        If att.Type = olByValue Then
            nome = Format$(i, "00") & "_" & SanitizarNome(SafeText(att.FileName))
            caminho = pasta & "\" & nome
            att.SaveAsFile caminho

            If Len(lista) > 0 Then lista = lista & ", "
            lista = lista & "{""nome"": " & JStr(SafeText(att.FileName)) & _
                    ", ""caminho"": " & JStr(caminho) & "}"
        End If
    Next i

    SalvarAnexos = lista
End Function

Private Function EmailRemetente(mail As Outlook.MailItem) As String
    Dim endereco As String
    endereco = SafeText(mail.SenderEmailAddress)

    ' Em Exchange o endereco pode vir como DN interno (/O=...), entao tenta o SMTP real.
    If InStr(endereco, "@") = 0 Then
        On Error Resume Next
        endereco = SafeText(mail.PropertyAccessor.GetProperty(PR_SMTP))
        On Error GoTo 0
    End If

    EmailRemetente = endereco
End Function

Private Sub GravarUtf8(caminho As String, texto As String)
    Dim st As Object
    Set st = CreateObject("ADODB.Stream")
    st.Type = 2                 ' adTypeText
    st.Charset = "utf-8"
    st.Open
    st.WriteText texto
    st.SaveToFile caminho, 2    ' adSaveCreateOverWrite
    st.Close
End Sub

Private Function JStr(ByVal s As String) As String
    s = Replace(s, "\", "\\")
    s = Replace(s, """", "\""")
    s = Replace(s, vbCrLf, "\n")
    s = Replace(s, vbCr, "\n")
    s = Replace(s, vbLf, "\n")
    s = Replace(s, vbTab, "\t")
    JStr = """" & s & """"
End Function

Private Function SafeText(ByVal v As Variant) As String
    If IsNull(v) Then
        SafeText = ""
    Else
        SafeText = CStr(v)
    End If
End Function

Private Function SanitizarNome(ByVal s As String) As String
    Dim ruins As Variant
    Dim i As Long

    ruins = Array("\", "/", ":", "*", "?", """", "<", ">", "|")
    For i = LBound(ruins) To UBound(ruins)
        s = Replace(s, CStr(ruins(i)), "-")
    Next i

    If Len(s) = 0 Then s = "anexo"
    SanitizarNome = s
End Function
