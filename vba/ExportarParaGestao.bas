Attribute VB_Name = "modExportarGestao"
Option Explicit

' =====================================================================
' ENVIAR E-MAIL PARA O SISTEMA GESTAO DE DEMANDAS (Python)
' Outlook classico -> pacote JSON + anexos na pasta de entrada (inbox).
'
' O que faz:
'   - exporta assunto, remetente, data, corpo e anexos do e-mail selecionado
'   - grava um .json na pasta de entrada (e os anexos numa subpasta)
'   - o sistema Python importa esses pacotes pelo botao "Importar e-mails"
'
' Nao envia, nao responde e nao altera o e-mail.
' =====================================================================

' Pasta de dados do sistema (a fila fica em <pasta de dados>\inbox).
'
' A macro NAO tem caminho fixo: usa a mesma pasta que o programa estiver
' usando, inclusive em outro computador. Ordem de resolucao:
'   1. variavel de ambiente GESTAO_DEMANDAS_DADOS (mesma variavel do programa);
'   2. DADOS_FIXO, se voce preencher esta constante (forca um caminho manual);
'   3. registro gravado pelo programa a cada execucao:
'      %LOCALAPPDATA%\Gestao de Demandas\ultima_pasta.txt
'      (funciona em qualquer pasta e computador - basta abrir o programa uma
'      vez depois de copia-lo);
'   4. %LOCALAPPDATA%\Gestao de Demandas\dados (padrao do programa quando nao
'      ha pasta de dados ao lado do executavel).
'
' Para conferir o caminho em uso, rode a macro MostrarPastaEntrada.
Private Const DADOS_FIXO As String = ""
Private Const TITULO As String = "Gestao de Demandas"
Private Const PR_SMTP As String = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
Private Const ARQUIVO_REGISTRO As String = "\Gestao de Demandas\ultima_pasta.txt"

' Pasta padrao por usuario, usada quando nao ha melhor referencia.
Private Function PastaPadraoUsuario() As String
    Dim base As String
    base = Environ$("LOCALAPPDATA")
    If Len(base) = 0 Then base = Environ$("APPDATA")
    If Len(base) = 0 Then base = Environ$("USERPROFILE")
    PastaPadraoUsuario = base & "\Gestao de Demandas\dados"
End Function

' Le a pasta que o programa registrou na ultima execucao.
Private Function PastaRegistrada() As String
    Dim caminho As String
    Dim st As Object
    Dim texto As String

    caminho = Environ$("LOCALAPPDATA")
    If Len(caminho) = 0 Then Exit Function
    caminho = caminho & ARQUIVO_REGISTRO
    If Dir$(caminho) = "" Then Exit Function

    On Error GoTo SemRegistro
    Set st = CreateObject("ADODB.Stream")
    st.Type = 2                 ' adTypeText
    st.Charset = "utf-8"
    st.Open
    st.LoadFromFile caminho
    texto = st.ReadText(-1)     ' adReadAll
    st.Close
    Set st = Nothing
    On Error GoTo 0

    PastaRegistrada = Trim$(texto)
SemRegistro:
End Function

' De onde veio o caminho (usado apenas na mensagem de diagnostico).
Private Function OrigemPasta() As String
    If Len(Trim$(Environ$("GESTAO_DEMANDAS_DADOS"))) > 0 Then
        OrigemPasta = "variavel GESTAO_DEMANDAS_DADOS"
    ElseIf Len(DADOS_FIXO) > 0 Then
        OrigemPasta = "constante DADOS_FIXO da macro"
    ElseIf Len(PastaRegistrada()) > 0 Then
        OrigemPasta = "registro do programa"
    Else
        OrigemPasta = "padrao do usuario"
    End If
End Function

' Retorna a pasta de dados em uso (sem barra final).
Private Function PastaDados() As String
    Dim base As String
    base = Trim$(Environ$("GESTAO_DEMANDAS_DADOS"))
    If Len(base) = 0 Then base = Trim$(DADOS_FIXO)
    If Len(base) = 0 Then base = PastaRegistrada()
    If Len(base) = 0 Then base = PastaPadraoUsuario()
    Do While Len(base) > 0 And Right$(base, 1) = "\"
        base = Left$(base, Len(base) - 1)
    Loop
    PastaDados = base
End Function

' Retorna a pasta de entrada (fila) em uso.
Private Function InboxPath() As String
    InboxPath = PastaDados() & "\inbox"
End Function

' Mostra onde a macro esta gravando (util quando o programa foi copiado).
Public Sub MostrarPastaEntrada()
    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    MsgBox "Pasta de dados em uso:" & vbCrLf & PastaDados() & vbCrLf & vbCrLf & _
           "Origem: " & OrigemPasta() & vbCrLf & _
           "Fila de e-mails:" & vbCrLf & InboxPath() & vbCrLf & vbCrLf & _
           "Existe: " & IIf(fso.FolderExists(InboxPath()), "sim", "nao"), _
           vbInformation, TITULO
    If fso.FolderExists(InboxPath()) Then
        Shell "explorer.exe """ & InboxPath() & """", vbNormalFocus
    End If
End Sub

Public Sub EnviarParaGestao()
    On Error GoTo ErrHandler

    Dim mail As Outlook.MailItem
    Set mail = SelecionarEmail()
    If mail Is Nothing Then Exit Sub

    Dim inbox As String
    inbox = InboxPath()

    Dim fso As Object
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FolderExists(inbox) Then
        MsgBox "Pasta de entrada nao encontrada:" & vbCrLf & inbox & vbCrLf & vbCrLf & _
               "Abra o Gestao de Demandas uma vez neste computador: ele cria a " & _
               "pasta e avisa a macro onde ela fica." & vbCrLf & vbCrLf & _
               "(Se preferir fixar o caminho, preencha DADOS_FIXO na macro ou a " & _
               "variavel GESTAO_DEMANDAS_DADOS.)", vbCritical, TITULO
        Exit Sub
    End If

    Dim idEnvio As String
    idEnvio = Format$(Now, "yyyymmdd_hhnnss")

    Dim pastaAnexos As String
    pastaAnexos = inbox & "\" & idEnvio & "_anexos"

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

    GravarUtf8 inbox & "\" & idEnvio & ".json", json

    MsgBox "E-mail enviado para a fila do sistema." & vbCrLf & vbCrLf & _
           "Assunto: " & SafeText(mail.Subject) & vbCrLf & _
           "Anexos: " & mail.Attachments.Count & vbCrLf & _
           "Pasta: " & inbox & vbCrLf & vbCrLf & _
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
