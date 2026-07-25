# Diagrama ER — data/filmes.sqlite

Modelo relacional do banco de filmes (IMDb Top 1000), com 3 tabelas.

```mermaid
erDiagram
    filmes ||--o{ filme_genero : "possui"
    filmes ||--o{ filme_ator   : "possui"
    filmes ||--o{ roteiro_chunk : "indexado (tem_roteiro=1)"

    filmes {
        INTEGER id             PK "identificador do filme"
        TEXT    titulo             "titulo original em ingles, ex.: The Godfather"
        INTEGER ano                "ano de lancamento"
        TEXT    certificado        "classificacao etaria (U, A, R, PG-13...)"
        INTEGER duracao_min        "duracao em minutos"
        REAL    nota_imdb          "nota IMDb (0-10)"
        INTEGER metascore          "Metascore (0-100), pode ser NULL"
        INTEGER votos              "numero de votos no IMDb"
        INTEGER bilheteria_usd     "bilheteria bruta em dolares (USD), pode ser NULL"
        TEXT    diretor            "nome do diretor"
        TEXT    sinopse            "sinopse, em ingles"
        INTEGER tem_roteiro        "1 se o roteiro esta no indice de busca"
    }

    filme_genero {
        INTEGER filme_id FK "referencia filmes.id"
        TEXT    genero      "ex.: Drama, Comedy, Sci-Fi"
    }

    filme_ator {
        INTEGER filme_id FK "referencia filmes.id"
        TEXT    ator        "nome do ator"
        INTEGER posicao     "1 a 4, ordem de credito"
    }

    roteiro_chunk {
        TEXT    id          PK "slug(titulo)-cena-parte"
        INTEGER filme_id    FK "= filmes.id"
        TEXT    filme          "titulo do filme"
        INTEGER ano            "ano de lancamento"
        INTEGER cena           "numero da cena"
        TEXT    personagens    "personagens presentes no trecho"
        TEXT    texto          "trecho do roteiro"
        BLOB    embedding      "vetor fastembed bge-base"
    }
```

## Como ler o diagrama (notação crow's-foot)

Mermaid usa a notação "pé de galinha" (crow's-foot) para relacionamentos.
Cada lado da linha tem um símbolo que indica quantas linhas daquela tabela
podem participar da relação:

- `||` = exatamente um (obrigatório)
- `o{` = zero ou muitos
- `|{` = um ou muitos

Assim, `filmes ||--o{ filme_genero` lê-se: **um** filme (`||`) está associado
a **zero ou muitos** registros de `filme_genero` (`o{`). Ou seja, é uma
relação **1 para N**: cada linha de `filme_genero`/`filme_ator` pertence a
exatamente um filme, mas um filme pode ter várias linhas nessas tabelas.

- **PK** = chave primária (identifica a linha).
- **FK** = chave estrangeira (aponta para a chave primária de outra tabela).

## Estrutura das tabelas

- **`filmes`** é a tabela central: 1 linha por filme, 1000 no total. `id` é a
  chave primária (PK).
- **`filme_genero`** guarda os gêneros de cada filme (um filme pode ter mais
  de um gênero). `filme_id` é chave estrangeira (FK) para `filmes.id`.
- **`filme_ator`** guarda o elenco principal de cada filme (até 4 atores,
  ordenados por `posicao`). `filme_id` é chave estrangeira (FK) para
  `filmes.id`.

## Exemplos de junção (JOIN)

```sql
-- generos de um filme
SELECT g.genero FROM filme_genero g
JOIN filmes f ON f.id = g.filme_id
WHERE f.titulo = 'Inception';

-- filmes em que um ator aparece
SELECT f.titulo, f.ano FROM filme_ator a
JOIN filmes f ON f.id = a.filme_id
WHERE a.ator = 'Tom Hanks'
ORDER BY f.ano;
```

> O schema canônico (usado pela tool de consulta SQL) vive em
> `utils/database.py`; este diagrama é a mesma estrutura em forma visual,
> para consulta rápida.

## A base vetorial (`roteiro_chunk`)

`roteiro_chunk` **não é uma tabela do SQLite** — é a coleção vetorial do
ChromaDB (`data/chroma/`), usada para busca semântica nos roteiros. Cada
registro é um trecho (chunk) de roteiro com seu embedding, criado por
`scripts/build_index.py`. O campo `filme_id` é a ponte entre os dois bancos:
é o mesmo `INTEGER` de `filmes.id`. Apenas os filmes com
`tem_roteiro = 1` em `filmes` têm chunks correspondentes em `roteiro_chunk`.
